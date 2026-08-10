# Text evidence: Table 6

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 21
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [63.109, 86.084, 513.222, 496.155]

## Caption

Table 6. Network science methods for detecting coordinated behavior based on content networks, where nodes are posted contents and edge weights encode the similarity between the linked contents. For each group of works we report the types of content, similarity functions, filtering criteria, and the community detection methods.

## Text from suggested visual region

~~~text
Table 6. Network science methods for detecting coordinated behavior based on content networks, where nodes are posted contents
and edge weights encode the similarity between the linked contents. For each group of works we report the types of content, similarity
functions, filtering criteria, and the community detection methods.

        reference     nodes             similarity                         filters†          community detection

          [5]              texts               cosine similarity TF-DID
         [64]             texts                 text similarity scores             threshold           loose strict campaign, cohesive campaign
         [141]             texts, hashtags      cosine similarity, cardinality    EDO, threshold      hierarchical clustering
          [26, 146]       hashtags             cardinality                      threshold          Louvain
          [24, 25]         cashtags             cardinality                      threshold
         [99]           images             Euclidean distance          kNN graph         Louvain
          [1]           comments         message similarity             Louvain

        † EDO: evenly distributed overlapping time window

  The works presented in Table 5 performed community discovery on a multiplex coordination network. Some authors

reduced the complexity of dealing with multiplex networks by flattening them into single layer networks where nodes

and edges are the union of the nodes and edges of each layer. Flattened networks can be either weighted [94] or

unweighted [29, 70, 96], with the latter resulting in the loss of some information. Alternative approaches involve

representing the multiplex network as a single-layer multigraph with labeled parallel edges [48], leveraging multi-view

clustering to combine different network layers [72, 73], or applying Louvain on each layer and an iterative probabilistic

voting consensus algorithm to achieve consensus clustering [32]. Only a couple of works exploit the multiplex version

of Leiden [52], Infomap [81], and Louvain [81], fully exploiting the multimodal structure of the coordination network.

4.1.5  Content networks. A few works built and analyzed networks of content rather than users. After selecting the
initial set of users, these methods build a fully connected network where the nodes are contents posted by the users

(e.g., posts) and edge weights are proportional to the similarity between the linked contents. The community discovery

process on a content network yields clusters of highly similar contents, regarded as proxies for coordination. User and

content networks are interchangeable because each node in a user network can be mapped to the content they published,

and each node in a content network can be mapped to its respective author, allowing for a dual representation of the

same underlying actions. The main characteristics of the works based on content networks are reported in Table 6. Some

works built and analyzed content networks where the nodes were Twitter cashtags [24, 25], or hashtags [26, 146]. Edge

weights were given by the number of co-occurrences of the cashtags and hashtags in the same tweets. The analyses

revealed suspicious clusters of contents that were later linked to online manipulations by coordinated actors. Other

works created a network of similar texts [5 64] or comments [1] published by multiple users Lee et al [64] identify
~~~

## Body references

- [PDF p.21] same underlying actions. The main characteristics of the works based on content networks are reported in Table 6. Some

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
