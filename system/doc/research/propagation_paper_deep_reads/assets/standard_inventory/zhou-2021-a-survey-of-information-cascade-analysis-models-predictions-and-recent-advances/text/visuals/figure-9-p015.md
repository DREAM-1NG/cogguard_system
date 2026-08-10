# Text evidence: Figure 9

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 15
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [35.679, 73.663, 450.24, 263.737]

## Caption

Fig. 9. Left: a global graph retrieved from the five largest cascades in Weibo dataset. It contains 262,458 nodes and 324,540 edges. Edges from different cascades are in different colors. We can clearly see that these cascades are not isolated. Right: an example of 1-reachable graph retrieved from Weibo dataset. Dark nodes (red) come from a cascade graph Gc, where pale nodes are neighbors of the red nodes.

## Text from suggested visual region

~~~text
Fig. 9. Left: a global graph retrieved from the five largest cascades in Weibo dataset. It contains 262,458
nodes and 324,540 edges. Edges from different cascades are in different colors. We can clearly see that these
cascades are not isolated. Right: an example of 1-reachable graph retrieved from Weibo dataset. Dark nodes
(red) come from a cascade graph Gc, where pale nodes are neighbors of the red nodes.

f  ll             f  ll       h    l     h    b l      f   d  l  h       l       l     h     l b  l    h [
~~~

## Body references

- [PDF p.14] The left portion of Figure 9 shows an example of global graph, which is composed of the five largest cascades in the Weibo dataset. Nodes in the graph are individual users while edges represent the retweeting relationships between users. As it shows, a large number of users not only partic- ipate in one cascade but also act as bridges between separate cascades. The historical behaviors, personal preferences, and communities of users can further help us to identify the roles of users in the cascade graphs [191, 208]. A complete global graph can be very large, e.g., a retweeting global graph retrieved from Weibo has more than 6M nodes (users) and 15M edges (retweet actions), while the citing global graph retrieved from APS has 422K nodes (authors) and 54M edges (cite actions). It is noteworthy that nodes in cascade graph may not necessarily appear in the global graph. For example, in Twitter, a user can retweet posts from other users who are not her/his
- [PDF p.15] The right portion of Figure 9 shows an example of r-reachable graph (r = 1), where dark nodes and their interactions form the cascade graph. r-reachable graph tells us how many nodes are exposed to the active nodes and their topology. The rationale behind modeling an r-reachable graph is that the highly exposed nodes would potentially bring more nodes into this cascade in the future [61].

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
