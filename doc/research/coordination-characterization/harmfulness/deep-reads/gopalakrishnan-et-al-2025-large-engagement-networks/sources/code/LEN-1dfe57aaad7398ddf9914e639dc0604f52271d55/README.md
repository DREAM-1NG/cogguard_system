# Large Engagement Networks for Classifying Coordinated Campaigns and Organic Twitter Trends

### Overview
Our dataset(LEN) is a graph classification benchmark of Turkish Twitter engagement networks to help identify campaign graphs and other downstream tasks or identifying the type of campaign. The data is publicly available [here](https://erdemub.github.io/large-engagement-network/).
### Dataset Description
LEN, consists of an overall dataset and a small dataset. 
**Small Dataset (LEN-Small)**: The small dataset contains 51 campaign and 49 non-campaign networks. There are 6 sub-types in campaign and 7 in non-campaign. The following is a brief dataset description.

| Category        | Sub-types         | # graphs | Min nodes | Max nodes | Avg nodes | Min edges | Max edges | Avg edges |
|-----------------|-----------|----------|-----------|-----------|-----------|-----------|-----------|-----------|
| Campaign | Politics       | 62       | 100       | 50,286    | 6,570     | 203       | 71,704    | 10,210    |
|                 | Reform | 58       | 131       | 19,578    | 1,229     | 540       | 1,105,918 | 25,268    |
|                 | News             | 24       | 581       | 54,996    | 10,368    | 942       | 80,784    | 15,582    |
|                 | Finance          | 14       | 273       | 9,976     | 1,802     | 243       | 10,725    | 2,334     |
|                 | Noise            | 9        | 454       | 55,933    | 12,180    | 473       | 48,937    | 10,882    |
|                 | Cult             | 6        | 313       | 7,880     | 2,303     | 637       | 11,615    | 3,431     |
|                 | Entertainment    | 3        | 678       | 4,220     | 2,237     | 3,806     | 132,013   | 48,767    |
|                 | Common           | 3        | 3,487     | 9,974     | 5,919     | 2,818     | 9,470     | 7,066     |
| **Overall**     | **Campaign**     | **170**  | **100**   | **55,933**| **5,157** | **203**   | **1,105,918** | **16,006** |
| Non-Campaign | News             | 52       | 818       | 95,575    | 24,834    | 709       | 213,444   | 43,201    |
|                 | Sports           | 30       | 469       | 75,653    | 9,530     | 403       | 101,656   | 12,948    |
|                 | Festival         | 17       | 885       | 119,952   | 35,466    | 803       | 199,305   | 55,947    |
|                 | Internal         | 11       | 4,188     | 87,720    | 33,061    | 4,374     | 196,103   | 54,442    |
|                 | Common           | 10       | 1,214     | 64,320    | 17,079    | 1,270     | 99,306    | 24,869    |
|                 | Entertainment    | 8        | 1,477     | 20,060    | 7,289     | 1,712     | 45,211    | 12,578    |
|                 | Announced cam.   | 4        | 6,650     | 26,358    | 13,382    | 14,362    | 50,864    | 24,817    |
|                 | Sports cam.      | 3        | 2,880     | 4,661     | 3,654     | 4,451     | 7,367     | 5,534     |
| **Overall**     | **Non-Campaign** | **135**  | **469**   | **119,952**| **20,632**| **403**   | **213,444**| **33,765** |



**Overall Dataset (LEN)**: The overall dataset contains 305 large networks, 170 campaign and 135 non-campaign graphs. There are 7 sub-types in campaign and 8 in non-campaign. The following is a brief dataset description.

| Category        | Sub-types         | # graphs | Min nodes | Max nodes | Avg nodes | Min edges | Max edges | Avg edges |
|-----------------|-------------------|----------|-----------|-----------|-----------|-----------|-----------|-----------|
|Campaign | Politics       | 62       | 100       | 50,286    | 6,570     | 203       | 71,704    | 10,210    |
|                 | Reform           | 58       | 131       | 19,578    | 1,229     | 540       | 1,105,918 | 25,268    |
|                 | News             | 24       | 581       | 54,996    | 10,368    | 942       | 80,784    | 15,582    |
|                 | Finance          | 14       | 273       | 9,976     | 1,802     | 243       | 10,725    | 2,334     |
|                 | Noise            | 9        | 454       | 55,933    | 12,180    | 473       | 48,937    | 10,882    |
|                 | Cult             | 6        | 313       | 7,880     | 2,303     | 637       | 11,615    | 3,431     |
|                 | Entertainment    | 3        | 678       | 4,220     | 2,237     | 3,806     | 132,013   | 48,767    |
|                 | Common           | 3        | 3,487     | 9,974     | 5,919     | 2,818     | 9,470     | 7,066     |
| **Overall**     | **Campaign**     | **170**  | **100**   | **55,933**| **5,157** | **203**   | **1,105,918** | **16,006** |
|Non-Campaign | News             | 52       | 818       | 95,575    | 24,834    | 709       | 213,444   | 43,201    |
|                 | Sports           | 30       | 469       | 75,653    | 9,530     | 403       | 101,656   | 12,948    |
|                 | Festival         | 17       | 885       | 119,952   | 35,466    | 803       | 199,305   | 55,947    |
|                 | Internal         | 11       | 4,188     | 87,720    | 33,061    | 4,374     | 196,103   | 54,442    |
|                 | Common           | 10       | 1,214     | 64,320    | 17,079    | 1,270     | 99,306    | 24,869    |
|                 | Entertainment    | 8        | 1,477     | 20,060    | 7,289     | 1,712     | 45,211    | 12,578    |
|                 | Announced cam.   | 4        | 6,650     | 26,358    | 13,382    | 14,362    | 50,864    | 24,817    |
|                 | Sports cam.      | 3        | 2,880     | 4,661     | 3,654     | 4,451     | 7,367     | 5,534     |
| **Overall**     | **Non-Campaign** | **135**  | **469**   | **119,952**| **20,632**| **403**   | **213,444**| **33,765** |


### Environment Setup
To install the required packages, use the following command:
```
pip install -r requirements.txt
```
This file is in the root directory of the given project.

### Running Experiments
An example script to run the code is given here:
```
python3 train_twitter_MPNN.py --model GCN --data_type small --multivariate 0 --hidden_dim 256 --lr 0.001 --output_dim 2 --small_graphs_path ./small_graphs --all_graphs_path ./all_graphs
```
We have more scripts availabe in the run directory given [here](https://github.com/erdemUB/LEN/tree/main/run).




