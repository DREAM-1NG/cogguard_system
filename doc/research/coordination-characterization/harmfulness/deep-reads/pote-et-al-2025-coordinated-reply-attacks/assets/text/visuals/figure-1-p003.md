# Text evidence: Figure 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 3
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [309.5, 44.001, 568.015, 236.105]

## Caption

Figure 1: Data collection for the classifiers. The dashed line separated the last IO reply and the first successive tweet by the target.

## Text from suggested visual region

~~~text
Figure 1: Data collection for the classifiers. The dashed line
separated the last IO reply and the first successive tweet by
the target.
~~~

## Body references

- [PDF p.3] Classification Dataset To identify tweets targeted by coordinated replies (RQ2) and accounts that participate in such activity (RQ3), we consider targeted tweets as our positive examples. For corresponding negative examples, we collect control tweets posted by the same targets after the last IO reply. This ensures that the tweets in our control data did not receive any coordinated replies by IO accounts. Fig. 1 illustrates the data collection. As in the case of positive examples, we only retain con- trol tweets with five or more replies. In addition, to avoid bias due to the diverse activity of the targets, we collect from each target as many control tweets as targeted tweets. Specifically, we select control tweets that were posted im- mediately after the last IO reply, subject to the five-reply minimum. In cases where we could not obtain as many con- trol tweets as targeted tweets, we ensure a balanced dataset by keeping the most recent targeted tweets. Similar to the targeted tweets, we fetch all the replies to the control tweets and all replier metadata. The resulting classification dataset includes 3,866 targeted tweets and the same number of control tweets by 1,507 targets. The drop in the number of tweets compared to the target dataset is due to the various constraints outlined above: authors with deleted or suspended accounts, or with no original tweets af- ter the IO, were removed; only original tweets with at least five replies were considered; and original (targeted or con- trol) tweets were removed due to balancing. There are in to- tal 881,918 and 323,378 replie

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
