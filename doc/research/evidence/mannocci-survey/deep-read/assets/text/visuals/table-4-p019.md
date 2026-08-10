# Text evidence: Table 4

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 19
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [63.127, 86.153, 513.224, 483.127]

## Caption

Table 4. Time window types, their parameters, and their effect on valid co-actions. To the right, a sequence of actions occurs at times 𝑡1, . . . ,𝑡6. The same sequence results in different valid co-actions, marked by the µ lock icon, depending on the time window type.

## Text from suggested visual region

~~~text
Table 4. Time window types, their parameters, and their effect on valid co-actions. To the right, a sequence of actions occurs at times
𝑡1, . . . ,𝑡6. The same sequence results in different valid co-actions, marked by the µ lock icon, depending on the time window type.

        type                                parameters             action sequence and valid co-actions


                                                         Z
         adjacent                                òµ


                                                               Z
         evenly distributed overlapping                                   µ           òµ
                                          ò
                                                                   𝛿   O

                                                               Z
         action driven overlapping
                                          òµ           òµ        · µ ¸


                                                                      𝑡𝑖𝑡𝑖+1                    𝑡0   𝑡1   𝑡2                            𝑡3   𝑡4                  𝑡5          𝑡6         time


same time window. In other words, this filter corresponds to adding a further constraint to the actions that determine

the coordination, in that such actions must be temporally close to one another. Table 3 displays the type and length of

the time windows used in literature, along with the type of coordination network built. As shown in Tables 3 and 4,
time windows can be either adjacent [1, 3, 18, 65, 138, 145, 146] or overlapping. Furthermore, overlapping time windows
can be evenly distributed in time [3, 13, 17, 20, 47, 48, 59, 71–73, 81, 94–96, 103, 115, 116, 129], or action-driven—that is,
positioned based on the timings of the actions [14, 28, 29, 32, 41, 41–44, 49, 61, 62, 70, 102, 104, 110, 121, 141, 149, 152].

As shown in Table 4, in the latter case each time window starts when a relevant action occurs. In the former case instead,

the additional parameter step 𝛿< 𝑍defines the temporal offset between two consecutive time windows. The amount
of overlap 𝑂between two consecutive overlapping time windows is thus 𝑂= 𝑍−𝛿. Given a sequence of actions by
two or more users, the choice of time windows and their parameters influence the number of such actions that are
valid co-actions. These are indicated with the µ lock icon in the example shown in the rightmost column of Table 4.
Let 𝑑= 𝑡2 −𝑡1 be the delay with which user 𝑢2 performs an action at time 𝑡2, with respect to the same action that 𝑢1
performed at time 𝑡1. Independently of the type of time window, actions whose 𝑑> 𝑍are never considered as co-actions.
Then, actions with 𝑑≤𝑍are always co-actions when using action-driven overlapping time windows. Conversely,
actions with 𝑑≤𝑂are always co-actions when using evenly distributed overlapping time windows, and can possibly
be co-actions when 𝑂< 𝑑≤𝑍. Instead, with adjacent time windows, also actions that are close in time (i.e., 𝑑≪𝑍) are
occasionally not considered valid co-actions when they occur across the boundary between two windows as in the
~~~

## Body references

- [PDF p.19] As shown in Table 4, in the latter case each time window starts when a relevant action occurs. In the former case instead,
- [PDF p.19] valid co-actions. These are indicated with the µ lock icon in the example shown in the rightmost column of Table 4.
- [PDF p.19] case of the actions occurred at 𝑡3 and 𝑡4 in the example of Table 4. Therefore, using overlapping rather than adjacent

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
