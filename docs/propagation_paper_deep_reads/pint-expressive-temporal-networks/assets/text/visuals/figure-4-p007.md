# Text evidence: Figure 4

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 7
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [303.085, 236.862, 514.003, 639.206]

## Caption

Figure 4: The effect of (u, v, t) on the monotone TCT of v. Also, note how the positional features of a node i, relative to v, can be incrementally updated.

## Text from suggested visual region

~~~text
ays to achieve injective temporal MP — we have
nductive bias of real-world temporal networks.
er of PINT, we propose augmenting memory states
 count how many temporal walks of a given length
 any times nodes appear at different levels of TCTs.
by padding a (d −1)-dimensional identity matrix
umn. Also, let r(t)    Nd denote the positional             j!u 2 at time t.  For each event (u, v, t), with u and
cursively update the positional feature vectors as

      u  =                          v                           u                (9) )      V(t+)              V(t+)                 v  = V(t)                 [ V(t)
      r(t+) = P r(t) + r(t)         u      (10) )    i!v      i!u   i!v  8i 2 V(t)
      r(t+) = P r(t) + r(t)           v      (11)     j!u     j!v   j!u  8j 2 V(t)
  t. The set Vi keeps track of the nodes for which ticipates in an interaction. For simplicity, we have
u or v at time t. Appendix B.10 provides equations
 in multiple events at the same timestamp.

 ) corresponds
 o i in k steps
 e in Lemma 2
erms of the so-
gard, Figure 4
 t (u, v, t) and
  10-11. The
CT of u to the

 me t, denoted
 t. for any path   Figure 4: The effect of (u, v, t) on the
               monotone TCT of v. Also, note how the
nodes of ˜Tu(t)                   positional features of a node i, relative
 1 > t2 > . . . .  to v, can be incrementally updated.
ral graph G(t), the k-th component of the positional
~~~

## Body references

- [PDF p.7] i!v) corresponds to how many different ways we can get from v to i in k steps through temporal walks. Additionally, we provide in Lemma 2 an interpretation of relative positional features in terms of the so- called monotone TCTs (Deﬁnition 2). In this regard, Figure 4 shows how the TCT of v evolves due to an event (u, v, t) and provides an intuition about the updates in Eqs. 10-11. The procedure amounts to appending the monotone TCT of u to the ﬁrst level of the monotone TCT of v.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
