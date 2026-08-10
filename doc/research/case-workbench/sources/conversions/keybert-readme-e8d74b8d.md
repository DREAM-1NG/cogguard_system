[![PyPI Downloads](https://camo.githubusercontent.com/716301542c54a74d7667b0092b65444f29534d1b5c503f528c61d6a529336e05/68747470733a2f2f7374617469632e706570792e746563682f62616467652f6b657962657274)](https://pepy.tech/projects/keybert)
[![PyPI - Python](https://camo.githubusercontent.com/93a33cfc2339ec3fa9be792576576fbaafc42b0c7031285662b02f3aca1e1c59/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f707974686f6e2d332e31302b2d626c75652e737667)](https://pypi.org/project/keybert/)
[![PyPI - License](https://camo.githubusercontent.com/8bb50fd2278f18fc326bf71f6e88ca8f884f72f179d3e555e20ed30157190d0d/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f6c6963656e73652d4d49542d677265656e2e737667)](https://github.com/MaartenGr/keybert/blob/master/LICENSE)
[![PyPI - PyPi](https://camo.githubusercontent.com/3a6d4724f7d00bb69d3a8a98cf2525bf4c8aa1bce39cc1f5c237dcd89adf9a94/68747470733a2f2f696d672e736869656c64732e696f2f707970692f762f6b657942455254)](https://pypi.org/project/keybert/)
[![Build](https://camo.githubusercontent.com/a7232c67cd9a65c699c0ba5d254abcb57e6ce7b8502969bf9b9cdce39f42e4f5/68747470733a2f2f696d672e736869656c64732e696f2f6769746875622f616374696f6e732f776f726b666c6f772f7374617475732f4d61617274656e47722f6b6579424552542f74657374696e672e796d6c3f6272616e63683d6d6173746572)](https://pypi.org/keybert/)
[![Open In Colab](https://camo.githubusercontent.com/eff96fda6b2e0fff8cdf2978f89d61aa434bb98c00453ae23dd0aab8d1451633/68747470733a2f2f636f6c61622e72657365617263682e676f6f676c652e636f6d2f6173736574732f636f6c61622d62616467652e737667)](https://colab.research.google.com/drive/1OxpgwKqSzODtO3vS7Xe1nEmZMCAIMckX?usp=sharing)

[![](images/logo.png)](images/logo.png)

# KeyBERT

KeyBERT is a minimal and easy-to-use keyword extraction technique that leverages BERT embeddings to
create keywords and keyphrases that are most similar to a document.

Corresponding medium post can be found [here](https://towardsdatascience.com/keyword-extraction-with-bert-724efca412ea).

## Table of Contents

1. [About the Project](#about)
2. [Getting Started](#gettingstarted)
   2.1. [Installation](#installation)
   2.2. [Basic Usage](#usage)
   2.3. [Max Sum Distance](#maxsum)
   2.4. [Maximal Marginal Relevance](#maximal)
   2.5. [Embedding Models](#embeddings)
3. [Large Language Models](#llms)

## 1. About the Project

[Back to ToC](#toc)

Although there are already many methods available for keyword generation
(e.g.,
[Rake](https://github.com/aneesha/RAKE),
[YAKE!](https://github.com/LIAAD/yake), TF-IDF, etc.)
I wanted to create a very basic, but powerful method for extracting keywords and keyphrases.
This is where **KeyBERT** comes in! Which uses BERT-embeddings and simple cosine similarity
to find the sub-phrases in a document that are the most similar to the document itself.

First, document embeddings are extracted with BERT to get a document-level representation.
Then, word embeddings are extracted for N-gram words/phrases. Finally, we use cosine similarity
to find the words/phrases that are the most similar to the document. The most similar words could
then be identified as the words that best describe the entire document.

KeyBERT is by no means unique and is created as a quick and easy method
for creating keywords and keyphrases. Although there are many great
papers and solutions out there that use BERT-embeddings
(e.g.,
[1](https://github.com/pranav-ust/BERT-keyphrase-extraction),
[2](https://github.com/ibatra/BERT-Keyword-Extractor),
[3](https://www.preprints.org/manuscript/201908.0073/download/final_file),
), I could not find a BERT-based solution that did not have to be trained from scratch and
could be used for beginners (**correct me if I'm wrong!**).
Thus, the goal was a `pip install keybert` and at most 3 lines of code in usage.

## 2. Getting Started

[Back to ToC](#toc)

### 2.1. Installation

Installation can be done using [pypi](https://pypi.org/project/keybert/):

```
pip install keybert
```

You may want to install more depending on the transformers and language backends that you will be using. The possible installations are:

```
pip install keybert[flair]
pip install keybert[gensim]
pip install keybert[spacy]
pip install keybert[use]
```

For a light-weight installation without PyTorch, run the following to make use of [Model2Vec](https://github.com/MinishLab/model2vec) instead:

```
pip install keybert --no-deps scikit-learn model2vec
```

### 2.2. Usage

The most minimal example can be seen below for the extraction of keywords:

```
from keybert import KeyBERT

doc = """
         Supervised learning is the machine learning task of learning a function that
         maps an input to an output based on example input-output pairs. It infers a
         function from labeled training data consisting of a set of training examples.
         In supervised learning, each example is a pair consisting of an input object
         (typically a vector) and a desired output value (also called the supervisory signal).
         A supervised learning algorithm analyzes the training data and produces an inferred function,
         which can be used for mapping new examples. An optimal scenario will allow for the
         algorithm to correctly determine the class labels for unseen instances. This requires
         the learning algorithm to generalize from the training data to unseen situations in a
         'reasonable' way (see inductive bias).
      """
kw_model = KeyBERT()
keywords = kw_model.extract_keywords(doc)
```

You can set `keyphrase_ngram_range` to set the length of the resulting keywords/keyphrases:

```
>>> kw_model.extract_keywords(doc, keyphrase_ngram_range=(1, 1), stop_words=None)
[('learning', 0.4604),
 ('algorithm', 0.4556),
 ('training', 0.4487),
 ('class', 0.4086),
 ('mapping', 0.3700)]
```

To extract keyphrases, simply set `keyphrase_ngram_range` to (1, 2) or higher depending on the number
of words you would like in the resulting keyphrases:

```
>>> kw_model.extract_keywords(doc, keyphrase_ngram_range=(1, 2), stop_words=None)
[('learning algorithm', 0.6978),
 ('machine learning', 0.6305),
 ('supervised learning', 0.5985),
 ('algorithm analyzes', 0.5860),
 ('learning function', 0.5850)]
```

We can highlight the keywords in the document by simply setting `highlight`:

```
keywords = kw_model.extract_keywords(doc, highlight=True)
```

[![](images/highlight.png)](images/highlight.png)

**NOTE**: For a full overview of all possible transformer models see [sentence-transformer](https://www.sbert.net/docs/pretrained_models.html).
I would advise either `"all-MiniLM-L6-v2"` for English documents or `"paraphrase-multilingual-MiniLM-L12-v2"`
for multi-lingual documents or any other language.

### 2.3. Max Sum Distance

To diversify the results, we take the 2 x top\_n words/phrases most similar to the document.
Among these words, we evaluate all possible `top_n`-combinations and select one combination
where words are least similar to each other by cosine similarity.

This has super-exponential time complexity and therefore not advised if you use a large `top_n`.

```
>>> kw_model.extract_keywords(doc, keyphrase_ngram_range=(3, 3), stop_words='english',
                              use_maxsum=True, nr_candidates=20, top_n=5)
[('set training examples', 0.7504),
 ('generalize training data', 0.7727),
 ('requires learning algorithm', 0.5050),
 ('supervised learning algorithm', 0.3779),
 ('learning machine learning', 0.2891)]
```

### 2.4. Maximal Marginal Relevance

To diversify the results, we can use Maximal Margin Relevance (MMR) to create
keywords / keyphrases which is also based on cosine similarity. The results
with **high diversity**:

```
>>> kw_model.extract_keywords(doc, keyphrase_ngram_range=(3, 3), stop_words='english',
                              use_mmr=True, diversity=0.7)
[('algorithm generalize training', 0.7727),
 ('labels unseen instances', 0.1649),
 ('new examples optimal', 0.4185),
 ('determine class labels', 0.4774),
 ('supervised learning algorithm', 0.7502)]
```

The results with **low diversity**:

```
>>> kw_model.extract_keywords(doc, keyphrase_ngram_range=(3, 3), stop_words='english',
                              use_mmr=True, diversity=0.2)
[('algorithm generalize training', 0.7727),
 ('supervised learning algorithm', 0.7502),
 ('learning machine learning', 0.7577),
 ('learning algorithm analyzes', 0.7587),
 ('learning algorithm generalize', 0.7514)]
```

### 2.5. Embedding Models

KeyBERT supports many embedding models that can be used to embed the documents and words:

* Sentence-Transformers
* Flair
* Spacy
* Gensim
* USE

Click [here](https://maartengr.github.io/KeyBERT/guides/embeddings.html) for a full overview of all supported embedding models.

**Sentence-Transformers**
You can select any model from `sentence-transformers` [here](https://www.sbert.net/docs/pretrained_models.html)
and pass it through KeyBERT with `model`:

```
from keybert import KeyBERT
kw_model = KeyBERT(model='all-MiniLM-L6-v2')
```

Or select a SentenceTransformer model with your own parameters:

```
from keybert import KeyBERT
from sentence_transformers import SentenceTransformer

sentence_model = SentenceTransformer("all-MiniLM-L6-v2")
kw_model = KeyBERT(model=sentence_model)
```

**Flair**
[Flair](https://github.com/flairNLP/flair) allows you to choose almost any embedding model that
is publicly available. Flair can be used as follows:

```
from keybert import KeyBERT
from flair.embeddings import TransformerDocumentEmbeddings

roberta = TransformerDocumentEmbeddings('roberta-base')
kw_model = KeyBERT(model=roberta)
```

You can select any ðŸ¤— transformers model [here](https://huggingface.co/models).

## 3. Large Language Models

[Back to ToC](#toc)

With `KeyLLM` you can new perform keyword extraction with Large Language Models (LLM). You can find the full documentation [here](https://maartengr.github.io/KeyBERT/guides/keyllm.html) but there are two examples that are common with this new method. Make sure to install the OpenAI package through `pip install openai` before you start.

First, we can ask OpenAI directly to extract keywords:

```
import openai
from keybert.llm import OpenAI
from keybert import KeyLLM

# Create your LLM
client = openai.OpenAI(api_key=MY_API_KEY)
llm = OpenAI(client)

# Load it in KeyLLM
kw_model = KeyLLM(llm)
```

This will query any ChatGPT model and ask it to extract keywords from text.

Second, we can find documents that are likely to have the same keywords and only extract keywords for those.
This is much more efficient then asking the keywords for every single documents. There are likely documents that
have the exact same keywords. Doing so is straightforward:

```
import openai
from keybert.llm import OpenAI
from keybert import KeyLLM
from sentence_transformers import SentenceTransformer

# Extract embeddings
model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(MY_DOCUMENTS, convert_to_tensor=True)

# Create your LLM
client = openai.OpenAI(api_key=MY_API_KEY)
llm = OpenAI(client)

# Load it in KeyLLM
kw_model = KeyLLM(llm)

# Extract keywords
keywords = kw_model.extract_keywords(MY_DOCUMENTS, embeddings=embeddings, threshold=.75)
```

You can use the `threshold` parameter to decide how similar documents need to be in order to receive the same keywords.

## Citation

To cite KeyBERT in your work, please use the following bibtex reference:

```
@misc{grootendorst2020keybert,
  author       = {Maarten Grootendorst},
  title        = {KeyBERT: Minimal keyword extraction with BERT.},
  year         = 2020,
  publisher    = {Zenodo},
  version      = {v0.3.0},
  doi          = {10.5281/zenodo.4461265},
  url          = {https://doi.org/10.5281/zenodo.4461265}
}
```

## References

Below, you can find several resources that were used for the creation of KeyBERT
but most importantly, these are amazing resources for creating impressive keyword extraction models:

**Papers**:

* Sharma, P., & Li, Y. (2019). [Self-Supervised Contextual Keyword and Keyphrase Retrieval with Self-Labelling.](https://www.preprints.org/manuscript/201908.0073/download/final_file)

**Github Repos**:

* <https://github.com/thunlp/BERT-KPE>
* <https://github.com/ibatra/BERT-Keyword-Extractor>
* <https://github.com/pranav-ust/BERT-keyphrase-extraction>
* <https://github.com/swisscom/ai-research-keyphrase-extraction>

**MMR**:
The selection of keywords/keyphrases was modeled after:

* <https://github.com/swisscom/ai-research-keyphrase-extraction>

**NOTE**: If you find a paper or github repo that has an easy-to-use implementation
of BERT-embeddings for keyword/keyphrase extraction, let me know! I'll make sure to
add a reference to this repo.