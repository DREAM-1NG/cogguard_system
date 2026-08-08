# Text evidence: Algorithm 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 14
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [21.42, 410.679, 590.58, 721.692]

## Caption

Algorithm 1: Training TGN

## Text from suggested visual region

~~~text
chronological order. It stores the last message for each node in a message store, to process it before
   predicting the next interaction for the node. This allows the memory-related modules to receive a
   gradient. Algorithm 1 presents the pseudocode for TGN training, while Figure 4 shows a schematic
  diagram of TGN.


  Algorithm 1: Training TGN
 1 s ←0 ;                              // Initialize memory to zeros
 2 m_raw ←{} ;                           // Initialize raw messages
 3 foreach batch (i, j, e, t) ∈training data do
 4   n ←sample negatives ;
 5  m ←msg(m_raw) ;         // Compute messages from raw features1
 6    ¯m ←agg(m) ;           // Aggregate messages for the same nodes
 7       ˆs ←mem( ¯m, s) ;                            // Get updated memory
 8     zi, zj, zn ←embˆs(i, t), embˆs(j, t), embˆs(n, t) ;  // Compute node embeddings3
 9    ppos, pneg ←dec(zi, zj), dec(zi, zn) ;      // Compute interactions probs
10       l = BCE(ppos, pneg) ;                           // Compute BCE loss
11    m_rawi, m_rawj ←(ˆsi,ˆsj, t, e), (ˆsj,ˆsi, t, e) ;      // Compute raw messages
12   m_raw ←store_raw_messages(m_raw, m_rawi, m_rawj) ;      // Store raw
     messages
13      si, sj ←ˆsi,ˆsj ;            // Store updated memory for sources and
     destinations
14 end


      1For the sake of clarity, we use the same message function for both sources and destination.
~~~

## Body references

- [PDF p.14] This issues motivate our training algorithm, which processes all interactions in batches following the chronological order. It stores the last message for each node in a message store, to process it before predicting the next interaction for the node. This allows the memory-related modules to receive a gradient. Algorithm 1 presents the pseudocode for TGN training, while Figure 4 shows a schematic diagram of TGN.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
