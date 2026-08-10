[![PyPI Downloads](https://camo.githubusercontent.com/6dca34a51cc951a5e4f047c2e3a1d6d027651411aa9a8f1327a0b1b3ef76176b/68747470733a2f2f7374617469632e706570792e746563682f62616467652f626572746f706963)](https://pepy.tech/projects/bertopic)
[![PyPI - Python](https://camo.githubusercontent.com/a78f0f48ae0745304c623bf01c5b6167334222a4b57f1e2f8aa17c5358c22935/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f707974686f6e2d76332e31302b2d626c75652e737667)](https://pypi.org/project/bertopic/)
[![Build](https://camo.githubusercontent.com/74930980acc54401e54efd48057bac77b94f0ce6859a29e597e15d32198e5cef/68747470733a2f2f696d672e736869656c64732e696f2f6769746875622f616374696f6e732f776f726b666c6f772f7374617475732f4d61617274656e47722f424552546f7069632f74657374696e672e796d6c3f6272616e63683d6d6173746572)](https://github.com/MaartenGr/BERTopic/actions)
[![docs](https://camo.githubusercontent.com/ab79123d57527a46120ff30f5be3c05cb691e4066c1701d641b6a1e29fef1d73/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f646f63732d50617373696e672d677265656e2e737667)](https://maartengr.github.io/BERTopic/)
[![PyPI - PyPi](https://camo.githubusercontent.com/8f25864d8f7838fcdd3cdec445c7a73fa03f9b2d332d9da34a4b2e04f13322b1/68747470733a2f2f696d672e736869656c64732e696f2f707970692f762f424552546f706963)](https://pypi.org/project/bertopic/)
[![PyPI - License](https://camo.githubusercontent.com/8bb50fd2278f18fc326bf71f6e88ca8f884f72f179d3e555e20ed30157190d0d/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f6c6963656e73652d4d49542d677265656e2e737667)](https://github.com/MaartenGr/VLAC/blob/master/LICENSE)
[![arXiv](https://camo.githubusercontent.com/ca89a7c5c5ee8fb6d257bbbd94aba6c126379702d22a3f5567d6f83a59f60e21/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f61725869762d323230332e30353739342d253343434f4c4f522533452e737667)](https://arxiv.org/abs/2203.05794)

# BERTopic

[![](images/logo.png)](images/logo.png)

BERTopic is a topic modeling technique that leverages ðŸ¤— transformers and c-TF-IDF to create dense clusters
allowing for easily interpretable topics whilst keeping important words in the topic descriptions.

BERTopic supports all kinds of topic modeling techniques:

|  |  |  |
| --- | --- | --- |
| [Guided](https://maartengr.github.io/BERTopic/getting_started/guided/guided.html) | [Supervised](https://maartengr.github.io/BERTopic/getting_started/supervised/supervised.html) | [Semi-supervised](https://maartengr.github.io/BERTopic/getting_started/semisupervised/semisupervised.html) |
| [Manual](https://maartengr.github.io/BERTopic/getting_started/manual/manual.html) | [Multi-topic distributions](https://maartengr.github.io/BERTopic/getting_started/distribution/distribution.html) | [Hierarchical](https://maartengr.github.io/BERTopic/getting_started/hierarchicaltopics/hierarchicaltopics.html) |
| [Class-based](https://maartengr.github.io/BERTopic/getting_started/topicsperclass/topicsperclass.html) | [Dynamic](https://maartengr.github.io/BERTopic/getting_started/topicsovertime/topicsovertime.html) | [Online/Incremental](https://maartengr.github.io/BERTopic/getting_started/online/online.html) |
| [Multimodal](https://maartengr.github.io/BERTopic/getting_started/multimodal/multimodal.html) | [Multi-aspect](https://maartengr.github.io/BERTopic/getting_started/multiaspect/multiaspect.html) | [Text Generation/LLM](https://maartengr.github.io/BERTopic/getting_started/representation/llm.html) |
| [Zero-shot **(new!)**](https://maartengr.github.io/BERTopic/getting_started/zeroshot/zeroshot.html) | [Merge Models **(new!)**](https://maartengr.github.io/BERTopic/getting_started/merge/merge.html) | [Seed Words **(new!)**](https://maartengr.github.io/BERTopic/getting_started/seed_words/seed_words.html) |

Corresponding medium posts can be found [here](https://medium.com/data-science/topic-modeling-with-bert-779f7db187e6?sk=0b5a470c006d1842ad4c8a3057063a99), [here](https://medium.com/data-science/using-whisper-and-bertopic-to-model-kurzgesagts-videos-7d8a63139bdf?sk=b1e0fd46f70cb15e8422b4794a81161d) and [here](https://medium.com/data-science/interactive-topic-modeling-with-bertopic-1ea55e7d73d8?sk=03c2168e9e74b6bda2a1f3ed953427e4). For a more detailed overview, you can read the [paper](https://arxiv.org/abs/2203.05794) or see a [brief overview](https://maartengr.github.io/BERTopic/algorithm/algorithm.html).

## Installation

Installation, with sentence-transformers, can be done using [uv](https://docs.astral.sh/uv/):

```
uv add bertopic
```

or with [pip](https://github.com/pypa/pip):

```
pip install bertopic
```

If you want to install BERTopic with other embedding models, you can choose one of the following:

```
# Choose an embedding backend
pip install bertopic[flair,gensim,spacy,use]

# Topic modeling with images
pip install bertopic[vision]
```

For a *light-weight installation* without transformers, UMAP and/or HDBSCAN (for training with Model2Vec or inference), see [this tutorial](https://maartengr.github.io/BERTopic/getting_started/tips_and_tricks/tips_and_tricks.html#lightweight-installation).

## Getting Started

For an in-depth overview of the features of BERTopic
you can check the [**full documentation**](https://maartengr.github.io/BERTopic/) or you can follow along
with one of the examples below:

| Name | Link |
| --- | --- |
| Start Here - **Best Practices in BERTopic** | [![Open In Colab](https://camo.githubusercontent.com/eff96fda6b2e0fff8cdf2978f89d61aa434bb98c00453ae23dd0aab8d1451633/68747470733a2f2f636f6c61622e72657365617263682e676f6f676c652e636f6d2f6173736574732f636f6c61622d62616467652e737667)](https://colab.research.google.com/drive/1BoQ_vakEVtojsd2x_U6-_x52OOuqruj2?usp=sharing) |
| **ðŸ†• New!** - Topic Modeling on Large Data (GPU Acceleration) | [![Open In Colab](https://camo.githubusercontent.com/eff96fda6b2e0fff8cdf2978f89d61aa434bb98c00453ae23dd0aab8d1451633/68747470733a2f2f636f6c61622e72657365617263682e676f6f676c652e636f6d2f6173736574732f636f6c61622d62616467652e737667)](https://colab.research.google.com/drive/1W7aEdDPxC29jP99GGZphUlqjMFFVKtBC?usp=sharing) |
| **ðŸ†• New!** - Topic Modeling with Llama 2 ðŸ¦™ | [![Open In Colab](https://camo.githubusercontent.com/eff96fda6b2e0fff8cdf2978f89d61aa434bb98c00453ae23dd0aab8d1451633/68747470733a2f2f636f6c61622e72657365617263682e676f6f676c652e636f6d2f6173736574732f636f6c61622d62616467652e737667)](https://colab.research.google.com/drive/1QCERSMUjqGetGGujdrvv_6_EeoIcd_9M?usp=sharing) |
| **ðŸ†• New!** - Topic Modeling with Quantized LLMs | [![Open In Colab](https://camo.githubusercontent.com/eff96fda6b2e0fff8cdf2978f89d61aa434bb98c00453ae23dd0aab8d1451633/68747470733a2f2f636f6c61622e72657365617263682e676f6f676c652e636f6d2f6173736574732f636f6c61622d62616467652e737667)](https://colab.research.google.com/drive/1DdSHvVPJA3rmNfBWjCo2P1E9686xfxFx?usp=sharing) |
| Topic Modeling with BERTopic | [![Open In Colab](https://camo.githubusercontent.com/eff96fda6b2e0fff8cdf2978f89d61aa434bb98c00453ae23dd0aab8d1451633/68747470733a2f2f636f6c61622e72657365617263682e676f6f676c652e636f6d2f6173736574732f636f6c61622d62616467652e737667)](https://colab.research.google.com/drive/1FieRA9fLdkQEGDIMYl0I3MCjSUKVF8C-?usp=sharing) |
| (Custom) Embedding Models in BERTopic | [![Open In Colab](https://camo.githubusercontent.com/eff96fda6b2e0fff8cdf2978f89d61aa434bb98c00453ae23dd0aab8d1451633/68747470733a2f2f636f6c61622e72657365617263682e676f6f676c652e636f6d2f6173736574732f636f6c61622d62616467652e737667)](https://colab.research.google.com/drive/18arPPe50szvcCp_Y6xS56H2tY0m-RLqv?usp=sharing) |
| Advanced Customization in BERTopic | [![Open In Colab](https://camo.githubusercontent.com/eff96fda6b2e0fff8cdf2978f89d61aa434bb98c00453ae23dd0aab8d1451633/68747470733a2f2f636f6c61622e72657365617263682e676f6f676c652e636f6d2f6173736574732f636f6c61622d62616467652e737667)](https://colab.research.google.com/drive/1ClTYut039t-LDtlcd-oQAdXWgcsSGTw9?usp=sharing) |
| (semi-)Supervised Topic Modeling with BERTopic | [![Open In Colab](https://camo.githubusercontent.com/eff96fda6b2e0fff8cdf2978f89d61aa434bb98c00453ae23dd0aab8d1451633/68747470733a2f2f636f6c61622e72657365617263682e676f6f676c652e636f6d2f6173736574732f636f6c61622d62616467652e737667)](https://colab.research.google.com/drive/1bxizKzv5vfxJEB29sntU__ZC7PBSIPaQ?usp=sharing) |
| Dynamic Topic Modeling with Trump's Tweets | [![Open In Colab](https://camo.githubusercontent.com/eff96fda6b2e0fff8cdf2978f89d61aa434bb98c00453ae23dd0aab8d1451633/68747470733a2f2f636f6c61622e72657365617263682e676f6f676c652e636f6d2f6173736574732f636f6c61622d62616467652e737667)](https://colab.research.google.com/drive/1un8ooI-7ZNlRoK0maVkYhmNRl0XGK88f?usp=sharing) |
| Topic Modeling arXiv Abstracts | [![Kaggle](https://camo.githubusercontent.com/87790dda10fe6ef1f7bc992c108bbc7746eb9d9941364b63f19855f926be0e68/68747470733a2f2f696d672e736869656c64732e696f2f7374617469632f76313f7374796c653d666f722d7468652d6261646765266d6573736167653d4b6167676c6526636f6c6f723d323232323232266c6f676f3d4b6167676c65266c6f676f436f6c6f723d323042454646266c6162656c3d)](https://www.kaggle.com/maartengr/topic-modeling-arxiv-abstract-with-bertopic) |

## Quick Start

We start by extracting topics from the well-known 20 newsgroups dataset containing English documents:

```
from bertopic import BERTopic
from sklearn.datasets import fetch_20newsgroups

docs = fetch_20newsgroups(subset='all',  remove=('headers', 'footers', 'quotes'))['data']

topic_model = BERTopic()
topics, probs = topic_model.fit_transform(docs)
```

After generating topics and their probabilities, we can access all of the topics together with their topic representations:

```
>>> topic_model.get_topic_info()

Topic	Count	Name
-1	4630	-1_can_your_will_any
0	693	49_windows_drive_dos_file
1	466	32_jesus_bible_christian_faith
2	441	2_space_launch_orbit_lunar
3	381	22_key_encryption_keys_encrypted
...
```

The `-1` topic refers to all outlier documents and are typically ignored. Each word in a topic describes the underlying theme of that topic and can be used
for interpreting that topic. Next, let's take a look at the most frequent topic that was generated:

```
>>> topic_model.get_topic(0)

[('windows', 0.006152228076250982),
 ('drive', 0.004982897610645755),
 ('dos', 0.004845038866360651),
 ('file', 0.004140142872194834),
 ('disk', 0.004131678774810884),
 ('mac', 0.003624848635985097),
 ('memory', 0.0034840976976789903),
 ('software', 0.0034415334250699077),
 ('email', 0.0034239554442333257),
 ('pc', 0.003047105930670237)]
```

Using `.get_document_info`, we can also extract information on a document level, such as their corresponding topics, probabilities, whether they are representative documents for a topic, etc.:

```
>>> topic_model.get_document_info(docs)

Document                               Topic	Name	                        Top_n_words                     Probability    ...
I am sure some bashers of Pens...	0	0_game_team_games_season	game - team - games...	        0.200010       ...
My brother is in the market for...      -1     -1_can_your_will_any	        can - your - will...	        0.420668       ...
Finally you said what you dream...	-1     -1_can_your_will_any	        can - your - will...            0.807259       ...
Think! It's the SCSI card doing...	49     49_windows_drive_dos_file	windows - drive - docs...	0.071746       ...
1) I have an old Jasmine drive...	49     49_windows_drive_dos_file	windows - drive - docs...	0.038983       ...
```

**`ðŸ”¥ Tip`**: Use `BERTopic(language="multilingual")` to select a model that supports 50+ languages.

## Fine-tune Topic Representations

In BERTopic, there are a number of different [topic representations](https://maartengr.github.io/BERTopic/getting_started/representation/representation.html) that we can choose from. They are all quite different from one another and give interesting perspectives and variations of topic representations. A great start is `KeyBERTInspired`, which for many users increases the coherence and reduces stopwords from the resulting topic representations:

```
from bertopic.representation import KeyBERTInspired

# Fine-tune your topic representations
representation_model = KeyBERTInspired()
topic_model = BERTopic(representation_model=representation_model)
```

However, you might want to use something more powerful to describe your clusters. You can even use ChatGPT or other models from OpenAI to generate labels, summaries, phrases, keywords, and more:

```
import openai
from bertopic.representation import OpenAI

# Fine-tune topic representations with GPT
client = openai.OpenAI(api_key="sk-...")
representation_model = OpenAI(client, model="gpt-4o-mini", chat=True)
topic_model = BERTopic(representation_model=representation_model)
```

**`ðŸ”¥ Tip`**: Instead of iterating over all of these different topic representations, you can model them simultaneously with [multi-aspect topic representations](https://maartengr.github.io/BERTopic/getting_started/multiaspect/multiaspect.html) in BERTopic.

## Visualizations

After having trained our BERTopic model, we can iteratively go through hundreds of topics to get a good
understanding of the topics that were extracted. However, that takes quite some time and lacks a global representation. Instead, we can use one of the [many visualization options](https://maartengr.github.io/BERTopic/getting_started/visualization/visualization.html) in BERTopic.
For example, we can visualize the topics that were generated in a way very similar to
[LDAvis](https://github.com/cpsievert/LDAvis):

```
topic_model.visualize_topics()
```

[![](images/topic_visualization.gif)](images/topic_visualization.gif)

## Modularity

By default, the [main steps](https://maartengr.github.io/BERTopic/algorithm/algorithm.html) for topic modeling with BERTopic are sentence-transformers, UMAP, HDBSCAN, and c-TF-IDF run in sequence. However, it assumes some independence between these steps which makes BERTopic quite modular. In other words, BERTopic not only allows you to build your own topic model but to explore several topic modeling techniques on top of your customized topic model:

BERTopicOverview.mp4

[
](https://private-user-images.githubusercontent.com/25746895/218420473-4b2bb539-9dbe-407a-9674-a8317c7fb3bf.mp4?jwt=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3ODYzNjAxOTgsIm5iZiI6MTc4NjM1OTg5OCwicGF0aCI6Ii8yNTc0Njg5NS8yMTg0MjA0NzMtNGIyYmI1MzktOWRiZS00MDdhLTk2NzQtYTgzMTdjN2ZiM2JmLm1wND9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFWQ09EWUxTQTUzUFFLNFpBJTJGMjAyNjA4MTAlMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjYwODEwVDExMDQ1OFomWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPWM2YjJmZGE1YmVhNDMyZTIxMzY2MTFjYWM2YzYyZjM3NDEzMzE0Y2E4NTgyNDc5MjM5MjAwODU2MmUyMzVkNjUmWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0JnJlc3BvbnNlLWNvbnRlbnQtdHlwZT12aWRlbyUyRm1wNCJ9.AeXbxIaxu_J8MOf-UqHXcabjz2vZ0sm5OWffMInnWKI)

You can swap out any of these models or even remove them entirely. The following steps are completely modular:

1. [Embedding](https://maartengr.github.io/BERTopic/getting_started/embeddings/embeddings.html) documents
2. [Reducing dimensionality](https://maartengr.github.io/BERTopic/getting_started/dim_reduction/dim_reduction.html) of embeddings
3. [Clustering](https://maartengr.github.io/BERTopic/getting_started/clustering/clustering.html) reduced embeddings into topics
4. [Tokenization](https://maartengr.github.io/BERTopic/getting_started/vectorizers/vectorizers.html) of topics
5. [Weight](https://maartengr.github.io/BERTopic/getting_started/ctfidf/ctfidf.html) tokens
6. [Represent topics](https://maartengr.github.io/BERTopic/getting_started/representation/representation.html) with one or [multiple](https://maartengr.github.io/BERTopic/getting_started/multiaspect/multiaspect.html) representations

## Functionality

BERTopic has many functions that quickly can become overwhelming. To alleviate this issue, you will find an overview
of all methods and a short description of its purpose.

### Common

Below, you will find an overview of common functions in BERTopic.

| Method | Code |
| --- | --- |
| Fit the model | `.fit(docs)` |
| Fit the model and predict documents | `.fit_transform(docs)` |
| Predict new documents | `.transform([new_doc])` |
| Access single topic | `.get_topic(topic=12)` |
| Access all topics | `.get_topics()` |
| Get topic freq | `.get_topic_freq()` |
| Get all topic information | `.get_topic_info()` |
| Get all document information | `.get_document_info(docs)` |
| Get representative docs per topic | `.get_representative_docs()` |
| Update topic representation | `.update_topics(docs, n_gram_range=(1, 3))` |
| Generate topic labels | `.generate_topic_labels()` |
| Set topic labels | `.set_topic_labels(my_custom_labels)` |
| Merge topics | `.merge_topics(docs, topics_to_merge)` |
| Reduce nr of topics | `.reduce_topics(docs, nr_topics=30)` |
| Reduce outliers | `.reduce_outliers(docs, topics)` |
| Find topics | `.find_topics("vehicle")` |
| Save model | `.save("my_model", serialization="safetensors")` |
| Load model | `BERTopic.load("my_model")` |
| Get parameters | `.get_params()` |

### Attributes

After having trained your BERTopic model, several attributes are saved within your model. These attributes, in part,
refer to how model information is stored on an estimator during fitting. The attributes that you see below all end in `_` and are
public attributes that can be used to access model information.

| Attribute | Description |
| --- | --- |
| `.topics_` | The topics that are generated for each document after training or updating the topic model. |
| `.probabilities_` | The probabilities that are generated for each document if HDBSCAN is used. |
| `.topic_sizes_` | The size of each topic |
| `.topic_mapper_` | A class for tracking topics and their mappings anytime they are merged/reduced. |
| `.topic_representations_` | The top *n* terms per topic and their respective c-TF-IDF values. |
| `.c_tf_idf_` | The topic-term matrix as calculated through c-TF-IDF. |
| `.topic_aspects_` | The different aspects, or representations, of each topic. |
| `.topic_labels_` | The default labels for each topic. |
| `.custom_labels_` | Custom labels for each topic as generated through `.set_topic_labels`. |
| `.topic_embeddings_` | The embeddings for each topic if `embedding_model` was used. |
| `.representative_docs_` | The representative documents for each topic if HDBSCAN is used. |

### Variations

There are many different use cases in which topic modeling can be used. As such, several variations of BERTopic have been developed such that one package can be used across many use cases.

| Method | Code |
| --- | --- |
| [Topic Distribution Approximation](https://maartengr.github.io/BERTopic/getting_started/distribution/distribution.html) | `.approximate_distribution(docs)` |
| [Online Topic Modeling](https://maartengr.github.io/BERTopic/getting_started/online/online.html) | `.partial_fit(doc)` |
| [Semi-supervised Topic Modeling](https://maartengr.github.io/BERTopic/getting_started/semisupervised/semisupervised.html) | `.fit(docs, y=y)` |
| [Supervised Topic Modeling](https://maartengr.github.io/BERTopic/getting_started/supervised/supervised.html) | `.fit(docs, y=y)` |
| [Manual Topic Modeling](https://maartengr.github.io/BERTopic/getting_started/manual/manual.html) | `.fit(docs, y=y)` |
| [Multimodal Topic Modeling](https://maartengr.github.io/BERTopic/getting_started/multimodal/multimodal.html) | `.fit(docs, images=images)` |
| [Topic Modeling per Class](https://maartengr.github.io/BERTopic/getting_started/topicsperclass/topicsperclass.html) | `.topics_per_class(docs, classes)` |
| [Dynamic Topic Modeling](https://maartengr.github.io/BERTopic/getting_started/topicsovertime/topicsovertime.html) | `.topics_over_time(docs, timestamps)` |
| [Hierarchical Topic Modeling](https://maartengr.github.io/BERTopic/getting_started/hierarchicaltopics/hierarchicaltopics.html) | `.hierarchical_topics(docs)` |
| [Guided Topic Modeling](https://maartengr.github.io/BERTopic/getting_started/guided/guided.html) | `BERTopic(seed_topic_list=seed_topic_list)` |
| [Zero-shot Topic Modeling](https://maartengr.github.io/BERTopic/getting_started/zeroshot/zeroshot.html) | `BERTopic(zeroshot_topic_list=zeroshot_topic_list)` |
| [Merge Multiple Models](https://maartengr.github.io/BERTopic/getting_started/merge/merge.html) | `BERTopic.merge_models([topic_model_1, topic_model_2])` |

### Visualizations

Evaluating topic models can be rather difficult due to the somewhat subjective nature of evaluation.
Visualizing different aspects of the topic model helps in understanding the model and makes it easier
to tweak the model to your liking.

| Method | Code |
| --- | --- |
| Visualize Topics | `.visualize_topics()` |
| Visualize Documents | `.visualize_documents()` |
| Visualize Document Hierarchy | `.visualize_hierarchical_documents()` |
| Visualize Topic Hierarchy | `.visualize_hierarchy()` |
| Visualize Topic Tree | `.get_topic_tree(hierarchical_topics)` |
| Visualize Topic Terms | `.visualize_barchart()` |
| Visualize Topic Similarity | `.visualize_heatmap()` |
| Visualize Term Score Decline | `.visualize_term_rank()` |
| Visualize Topic Probability Distribution | `.visualize_distribution(probs[0])` |
| Visualize Topics over Time | `.visualize_topics_over_time(topics_over_time)` |
| Visualize Topics per Class | `.visualize_topics_per_class(topics_per_class)` |

## Citation

To cite the [BERTopic paper](https://arxiv.org/abs/2203.05794), please use the following bibtex reference:

```
@article{grootendorst2022bertopic,
  title={BERTopic: Neural topic modeling with a class-based TF-IDF procedure},
  author={Grootendorst, Maarten},
  journal={arXiv preprint arXiv:2203.05794},
  year={2022}
}
```