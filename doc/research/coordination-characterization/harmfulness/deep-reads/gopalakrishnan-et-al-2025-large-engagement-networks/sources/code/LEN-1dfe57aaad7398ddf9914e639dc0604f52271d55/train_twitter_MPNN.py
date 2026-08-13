
import sys
# sys.path.append('/projects/academic/erdem/atulanan/twitter_analytics/CRaWl/')
import torch
import numpy as np
from torch_geometric.datasets import ZINC
import torch.nn.functional as F
from torch.nn import BCEWithLogitsLoss, CrossEntropyLoss
from torch.optim.lr_scheduler import StepLR
import json
import argparse
# from dataset import RetweetDataset
import glob
from torch_geometric.transforms import RandomLinkSplit, RandomNodeSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report
from sklearn.model_selection import train_test_split
from torch_geometric.loader import DataLoader, NeighborLoader
from torch_geometric.nn import GCNConv, GATConv, GINConv, GINEConv
from torch.nn import LazyLinear, Linear, Sequential, Dropout, LeakyReLU, Sigmoid
import torch.optim as optim
import random
from random import sample
from torch_geometric.utils import train_test_split_edges
import networkx as nx
from networkx.readwrite import json_graph
from torch_geometric.data import Dataset, Data
from torch.nn import (ModuleList, Linear, Conv1d, MaxPool1d, Embedding, ReLU,
                      Sequential, BatchNorm1d as BN)
from torch_geometric.nn import global_mean_pool
from torch_geometric.utils import to_networkx
import torch.nn as nn
from statistics import mean, stdev
import sys, os
import pickle
import shutil
import warnings
warnings.filterwarnings("ignore")


data_path = None
num_node_features = None
num_edge_features = None
num_classes = None
lr = None

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
criterion = None
multivariate = None
noise_graphs = []
classify_news = None

# opt = optim.Adam(model.parameters(), lr=1e-3)

def seed_everything(seed=1):
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


class GCN_edge(torch.nn.Module):
    def __init__(self, conv1, conv2):
        super().__init__()
        self.conv1 = conv1
        self.conv2 = conv2
        self.out = Sequential(
            LazyLinear(out_features=128),  # First lazy linear layer
            Sigmoid(),  # Leaky ReLU activation
            LazyLinear(out_features=num_classes),  # Second lazy linear layer
            Sigmoid()
        )

    def forward(self, x, edge_index, edge_attr):
        x = F.leaky_relu(self.conv1(x, edge_index, edge_attr))
        x = F.leaky_relu(self.conv2(x, edge_index, edge_attr))
        return x


# seed_everything(1)
class GCN(torch.nn.Module):
    def __init__(self, conv1, conv2):
        super().__init__()
        self.conv1 = conv1
        self.conv2 = conv2

        self.dropout = Dropout(0.4)
        self.out = Sequential(
            LazyLinear(out_features=128),  # First lazy linear layer
            Sigmoid(),  # Leaky ReLU activation
            LazyLinear(out_features=num_classes),  # Second lazy linear layer
            Sigmoid()
        )

    def forward(self, x, edge_index):
        x = F.leaky_relu(self.conv1(x, edge_index))
        x = F.leaky_relu(self.conv2(x, edge_index))
        return x



def load_split_data(data_path):
    print("Loading dataset.....")
    print(data_path)
    path = data_path
    train_data = None
    test_data = None
    val_data = None
    if multivariate:
        files = list(glob.glob(path+'/*_campaign_fulldata.json'))
    else:
        files = list(glob.glob(path + '/*.json'))

    data_list = []
    label_list = []

    campaign_news_graphs = []
    noncampaign_news_graphs = []

    if multivariate:
        with open(path + "/graph_labels_campaign.json", "r") as f:
            graph_labels = json.load(f)
    elif classify_news:
        with open(path+"/graph_labels_news.json", "r") as f:
            graph_labels = json.load(f)
    else:
        with open(path + "/graph_labels.json", "r") as f:
            graph_labels = json.load(f)

    label_counter = {1: 0, 0: 0}
    for file in files:
        # Get the graph label
        file_name = file.split('/')[-1][:-5]
        if file_name not in ['graph_labels', '#1MAYIS_noncampaign_fulldata'] and (file_name[:-9] in graph_labels):
            graph_label = graph_labels[file_name[:-9]]
            label_counter[graph_label]+=1
            with open(file, 'r') as f:
                data = json.load(f)
            graph = nx.DiGraph(json_graph.node_link_graph(data))

            mapping = {node: i for i, node in enumerate(graph.nodes())}
            graph = nx.relabel.relabel_nodes(graph, mapping)
            degrees = dict(graph.degree())
            label_list.append(graph_label)
            #print(graph_label)
            y = [graph_label]
            y = torch.tensor(y)
            x = torch.tensor([graph.nodes[node]['node_attr'] for node in graph.nodes()])
            edge_attr = torch.tensor([graph.edges[edge]['edge_attr'] for edge in graph.edges()])

            global num_edge_features, num_node_features
            num_node_features = x.shape[1]
            num_edge_features = edge_attr.shape[1]

            # get the correct list of attributes here
            edge_index = torch.tensor([e for e in graph.edges], dtype=torch.long)
            edge_weights = torch.tensor([degrees[i] * degrees[j] for i, j in graph.edges], dtype=torch.float)

            data = Data(x=x, edge_index=edge_index, y=y)
            data.y = data.y.view(-1)

            data.edge_attr = edge_attr
            data.edge_index = torch.transpose(data.edge_index, 0, 1)
            data.edge_weight = edge_weights
            if classify_news:
                if graph_label:
                    campaign_news_graphs.append(data)
                else:
                    noncampaign_news_graphs.append(data)
            else:
                data_list.append(data)

    if classify_news:
        data_list = campaign_news_graphs + sample(noncampaign_news_graphs, 24)
        label_list = [1]*len(campaign_news_graphs) + [0]*24

    if multivariate:
        label_list[-1] = 2
        label_list[-2] = 2
        label_list[-3] = 2
    train_data,test_data,train_labels,test_labels = train_test_split(data_list,label_list,stratify=label_list,test_size=0.25)
    return train_data, test_data, val_data

def load_data(data_path):
    # load all the json files that are campaign
    print("Loading graphs for noise classification")
    path = data_path
    train_data = []
    test_data = []
    val_data = None

    files = list(glob.glob(path + '/*_campaign_fulldata.json'))

    with open(path + "/graph_labels_campaign_noise.json", "r") as f:
        graph_labels = json.load(f)

    # check if the file is a noise graph or not
    for file in files:
        # Get the graph label
        file_name = file.split('/')[-1][:-5]
        #print(f"File name is {file_name}")
        if file_name not in ['graph_labels', '#1MAYIS_noncampaign_fulldata'] and (file_name in graph_labels):
            graph_label = graph_labels[file_name]
            with open(file, 'r') as f:
                data = json.load(f)
            graph = nx.DiGraph(json_graph.node_link_graph(data))

            mapping = {node: i for i, node in enumerate(graph.nodes())}
            graph = nx.relabel.relabel_nodes(graph, mapping)
            degrees = dict(graph.degree())

            y = [graph_label]
            y = torch.tensor(y)
            x = torch.tensor([graph.nodes[node]['node_attr'] for node in graph.nodes()])
            edge_attr = torch.tensor([graph.edges[edge]['edge_attr'] for edge in graph.edges()])

            global num_edge_features, num_node_features
            num_node_features = x.shape[1]
            num_edge_features = edge_attr.shape[1]

            # get the correct list of attributes here
            edge_index = torch.tensor([e for e in graph.edges], dtype=torch.long)
            edge_weights = torch.tensor([degrees[i] * degrees[j] for i, j in graph.edges], dtype=torch.float)

            data = Data(x=x, edge_index=edge_index, y=y)
            data.y = data.y.view(-1)

            data.edge_attr = edge_attr
            data.edge_index = torch.transpose(data.edge_index, 0, 1)
            data.edge_weight = edge_weights

            if(graph_label == 7):
                test_data.append(data)
                noise_graphs.append(file_name)
            else:
                train_data.append(data)
    # if noise graph move to test_list
    # else move to train list
    return train_data, test_data, val_data

def predict(model, test_data, args):
    y_pred = []
    y_actual = []
    y_scores = []
    prediction_counter = {}
    for graph in test_data:
        graph = graph.to(device)
        if args.model=="GINE":
            pred = model(graph.x, graph.edge_index, graph.edge_attr)
        else:
            pred = model(graph.x, graph.edge_index)
        pooled_output = global_mean_pool(pred, batch=None)
        pred = model.out(pooled_output)
        pred = F.softmax(pred, dim=1)
        pred = torch.sigmoid(pred)
        labels = graph.y
        _, predictions = torch.max(pred, 1)
        if predictions.item() not in prediction_counter:
            prediction_counter[predictions.item()]=1
        else:
            prediction_counter[predictions.item()]+=1
        y_pred += predictions.tolist()
        y_actual += labels.tolist()
        y_scores += pred[:, 1].tolist()
        # Load neighbours of each node to get a fair sample that can fit in the gpu
    y_pred = np.array(y_pred)
    y_actual = np.array(y_actual)
    y_scores = np.array(y_scores)

    print(f"Labels predicted are: {prediction_counter}")
    return y_pred, y_actual, y_scores


def val_model(model, val_data, args):
    model.eval()

    val_loss = 0
    counter = 0

    for graph in val_data:
        graph = graph.to(device)
        if args.model=="GINE":
            pred = model(graph.x, graph.edge_index, graph.edge_attr)
        else:
            pred = model(graph.x, graph.edge_index)
        pooled_output = global_mean_pool(pred, batch=None)
        pred = F.softmax(model.out(pooled_output), dim=1)

        # Generate Labels
        label = None
        if (multivariate):
            label = graph.y
            label = label.to(device)
        else:
            label = [0, 0]
            label[graph.y.item()] = 1
            label = torch.Tensor(label).unsqueeze(dim=0)
            label = label.to(device)

        loss = criterion(pred, label)
        val_loss += loss.item()
        counter += 1
    return val_loss / counter

def train_model(model, epochs, train_data, val_data, args):
    opt = optim.Adam(model.parameters(), lr=lr)

    train_loss_epochs = []
    val_loss_epochs = []

    for epoch in range(epochs):
        train_loss = 0
        val_loss = 0
        counter = 0
        for graph in train_data:
            graph = graph.to(device)
            if args.model=="GINE":
                x_val = torch.tensor(graph.x).to(torch.int64)
                pred = model(x_val, graph.edge_index, graph.edge_attr)
            else:
                pred = model(graph.x, graph.edge_index)

            pooled_output = global_mean_pool(pred, batch=None)
            pred = F.softmax(model.out(pooled_output),dim=1)
            # Generate Labels
            label = None
            if(multivariate):
                label = graph.y
                label = label.to(device)
            else:
                label = [0, 0]
                label[graph.y.item()] = 1
                label = torch.Tensor(label).unsqueeze(dim=0)
                label = label.to(device)

            pred = torch.sigmoid(pred)
            loss = criterion(pred, label)
            train_loss += loss.item()
            counter += 1

            loss.backward()
            opt.step()
            opt.zero_grad()
        train_loss /= counter

        #val_loss = val_model(model, val_data, args)
        train_loss_epochs.append(train_loss)
        #val_loss_epochs.append(val_loss)

    # print(f"Training loss: {train_loss}")
    return model, train_loss_epochs, val_loss_epochs

def evaluate(y_pred, y_actual):

    micro_f1 = None
    macro_f1= None
    precision = None
    recall = None
    accuracy = accuracy_score(y_actual, y_pred)
    if multivariate:

        precision = precision_score(y_actual, y_pred, average='weighted')
        recall = recall_score(y_actual, y_pred, average='weighted')
        micro_f1 = f1_score(y_actual, y_pred, average='micro')
        macro_f1 = f1_score(y_actual, y_pred, average='macro')
        return accuracy, precision, recall, micro_f1, macro_f1

    precision = precision_score(y_actual, y_pred)
    recall = recall_score(y_actual, y_pred)
    f1 = f1_score(y_actual, y_pred)

    # macro_f1 = f1_score(y_actual, y_pred, average='macro')

    return accuracy, precision, recall, f1

def getReport(y_pred,y_actual):
    report = classification_report(y_actual, y_pred)
    return report


if __name__ == '__main__':
    print("Inside Main")

    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='GCN', help="Enter model name")
    parser.add_argument("--lr", default=1e-4, help="Enter learning rate")
    parser.add_argument('--hidden_dim', default=128, help="Enter hidden dimensions")
    parser.add_argument('--output_dim', default=2, help="Enter output dimensions")
    parser.add_argument('--data_type', default='small', help="Either small or All")
    parser.add_argument('--edge_attr', default=0, help="Either small or All")
    parser.add_argument('--multivariate', default=0, help="Initialize if you are performing multivariate classification")
    parser.add_argument("--classify_noise", default=0, help="Classify the noise graphs")
    parser.add_argument("--classify_news", default=0, help="Classify the news graphs")
    parser.add_argument("--small_graphs_path",help="Mention path to small graphs")
    parser.add_argument("--all_graphs_path",help="Mention path to all graphs")


    args = parser.parse_args()
    model_name = args.model
    hidden_channels = int(args.hidden_dim) 
    num_classes = int(args.output_dim) 
    multivariate = int(args.multivariate)
    classify_noise = int(args.classify_noise)
    classify_news = int(args.classify_news)
    small_dir = args.small_graphs_path
    all_dir = args.all_graphs_path

    lr = float(args.lr)
    if not multivariate:
        criterion = BCEWithLogitsLoss()
    else:
        criterion = CrossEntropyLoss()
    if args.data_type == 'small':
        data_path = small_dir
    else:
        data_path = All_dir

    output_file_name = model_name + '_' +args.data_type+'.out'
    sys.stdout = output_file_name

    if classify_noise:
        train_data, test_data, val_data = load_data(data_path)
    else:
        train_data, test_data, val_data = load_split_data(data_path)
    print("Dataset loading done  ", data_path, len(train_data))
    epochs = 100

    print(f"Number of node features: {num_node_features} and number of edge features :{num_edge_features}")

    conv_dictionary = {'GCN': (GCNConv(num_node_features, hidden_channels),GCNConv(hidden_channels, hidden_channels)),
                       'GAT': (GATConv(num_node_features, hidden_channels),GATConv(hidden_channels, hidden_channels)),
                       'GIN': (GINConv(Sequential(Linear(num_node_features, hidden_channels), nn.LeakyReLU(0.2), Linear(hidden_channels, hidden_channels), nn.LeakyReLU(0.2),),train_eps=False),
                               GINConv(Sequential(Linear(hidden_channels, hidden_channels), nn.LeakyReLU(0.2), Linear(hidden_channels, hidden_channels), nn.LeakyReLU(0.2),),train_eps=False)),
                       'GINE': (GINEConv(Sequential(Linear(num_node_features, hidden_channels), nn.LeakyReLU(0.2), Linear(hidden_channels, hidden_channels), nn.LeakyReLU(0.2), ),train_eps=True,edge_dim=num_edge_features),
                               GINEConv(Sequential(Linear(hidden_channels, hidden_channels), nn.LeakyReLU(0.2), Linear(hidden_channels, hidden_channels), nn.LeakyReLU(0.2), ),train_eps=True,edge_dim=num_edge_features))
                       }

    all_results = []
    for exp in range(0, 5):
        seed_everything(exp)
        if model_name == "GINE":
            conv1 = conv_dictionary[model_name][0]
            conv2 = conv_dictionary[model_name][1]
            args.edge_attr = 0
            model = GCN_edge(conv1,conv2)
        else:
            conv1 = conv_dictionary[model_name][0]
            conv2 = conv_dictionary[model_name][1]
            args.edge_attr = 0
            model = GCN(conv1, conv2)
        model.to(device)
        model, train_loss_epochs, val_loss_epochs = train_model(model, epochs, train_data, val_data, args)
        y_pred, y_actual, y_scores = predict(model, test_data, args)

        if classify_noise:
            y_pred = y_pred.tolist()
            zipped_lists = zip(y_pred, noise_graphs)
            for y, graph in zipped_lists:
                print(y, graph)
            sys.exit()

        if(multivariate):
            acc, prec, rec, micro_f1, macro_f1 = evaluate(y_pred, y_actual)
            all_results.append([acc, prec, rec, micro_f1, macro_f1])
            #print(f"Model: {model_name}, Accuracy: {acc}, Precision: {prec}, Recall: {rec}, Micro-F1: {micro_f1}, Macro-F1: {macro_f1}")
        else:
            acc, prec, rec, f1 = evaluate(y_pred, y_actual)
            all_results.append([acc, prec, rec, f1])
            #print(f"Model: {model_name}, Accuracy: {acc}, Precision: {prec}, Recall: {rec}, F1: {f1}")


    if(multivariate):
        #print(all_results, np.mean(all_results, axis=0), np.std(all_results, axis=0))
        all_mean, all_std = np.round(np.mean(all_results, axis=0), 3), np.round(np.std(all_results, axis=0), 3)
        print(model_name, args.data_type)
        print(f'Accuracy: {all_mean[0]} ± {all_std[0]}')
        print(f'Precision: {all_mean[1]} ± {all_std[1]}')
        print(f'Recall: {all_mean[2]} ± {all_std[2]}')
        print(f'Micro-F1 Score: {all_mean[3]} ± {all_std[3]}, Macro-F1 Score: {all_mean[4]} ± {all_std[4]}')

    else:
        #print(all_results, np.mean(all_results, axis=0), np.std(all_results, axis=0))
        all_mean, all_std = np.round(np.mean(all_results, axis=0), 3), np.round(np.std(all_results, axis=0), 3)
        print(model_name, args.data_type)
        print(f'Accuracy: {all_mean[0]} ± {all_std[0]}')
        print(f'Precision: {all_mean[1]} ± {all_std[1]}')
        print(f'Recall: {all_mean[2]} ± {all_std[2]}')
        print(f'F1-Score: {all_mean[3]} ± {all_std[3]}')





