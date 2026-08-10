# Text evidence: Table 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 6
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [97.691, 502.81, 514.667, 772.157]

## Caption

Table 1: Previous models for deep learning on continuous-time dynamic graphs are speciﬁc case of our TGN framework. Shown are multiple variants of TGN used in our ablation studies. method (l,n) refers to graph convolution using l layers and n neighbors. †uses t-batches. ∗uses uniform sampling of neighbors, while the default is sampling the most recent neighbors. ‡message aggregation not explained in the paper. ∥uses a summary of the destination node neighborhood (obtained through graph attention) as additional input to the message function.

## Text from suggested visual region

~~~text
Table 1: Previous models for deep learning on continuous-time dynamic graphs are speciﬁc case of
our TGN framework. Shown are multiple variants of TGN used in our ablation studies. method (l,n)
refers to graph convolution using l layers and n neighbors. †uses t-batches. ∗uses uniform sampling
of neighbors, while the default is sampling the most recent neighbors. ‡message aggregation not
explained in the paper. ∥uses a summary of the destination node neighborhood (obtained through
graph attention) as additional input to the message function.

                Mem.  Mem. Updater   Embedding    Mess. Agg.   Mess. Func.
     Jodie          node     RNN           time       —†            id
    TGAT     —    —          attn (2l, 20n)∗   —     —
    DyRep         node     RNN              id        —‡           attn∥
     TGN-attn       node     GRU         attn (1l, 10n)         last             id
    TGN-2l        node     GRU         attn (2l, 10n)         last             id
    TGN-no-mem  —    —          attn (1l, 10n)   —     —
    TGN-time      node     GRU           time              last             id
    TGN-id        node     GRU              id               last             id
    TGN-sum      node     GRU      sum (1l, 10n)         last             id
    TGN-mean     node     GRU         attn (1l, 10n)     mean            id


                                       6
~~~

## Body references

- [PDF p.6] Most recent CTDGs learning models can be interpreted as speciﬁc cases of our framework (see Table 1). For example, Jodie (Kumar et al., 2019) uses the time projection embedding module emb(i, t) = (1 + ∆tw) ◦si(t). TGAT (Xu et al., 2020) is a speciﬁc case of TGN when the memory and its related modules are missing, and graph attention is used as the Embedding module. DyRep (Trivedi et al., 2019) computes messages using graph attention on the destination node neighbors. Finally, we note that TGN generalizes the Graph Networks (GN) model (Battaglia et al., 2018) for static graphs (with the exception of the global block that we omitted from our model for the sake of simplicity), and thus the majority of existing graph message passing-type architectures.
- [PDF p.8] We perform a detailed ablation study comparing different instances of our TGN framework, focusing on the speed vs accuracy tradeoff resulting from the choice of modules and their combination. The variants we experiment with are reported in Table 1 and their results are depicted in Figure 3a.
- [PDF p.16] When performing neighborhood sampling (Hamilton et al., 2017a) in static graphs, nodes are usually sampled uniformly. While this strategy is also possible for dynamic graphs, it turns out that the most recent edges are often the most informative. In Figure 5 we compare two TGN-attn models (see Table 1) with either uniform or most recent neighbor sampling, which shows that a model which samples the most recent edges obtains higher performances.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
