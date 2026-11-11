# Detailed Speech: Modeling and Evaluation Methodology

## Opening

Good morning everyone.

This slide explains how we model and evaluate the traffic-analysis problem. The important idea is that a high classification score is not automatically evidence of privacy leakage. We need to choose appropriate models, separate repeated captures correctly, compare the result with a chance baseline, and report enough metrics to understand both performance and uncertainty.

I will explain the four parts of the methodology: the classifier, the data split, the significance test, and the metrics we report.

## 1. Classifier

The first part is the classifier.

Our primary model is the **Random Forest**. Random Forest is appropriate because our input is tabular traffic-shape data. Each flow is represented by features such as packet counts, packet sizes, upstream and downstream bytes, timing values, inter-arrival times, burst statistics, and the signed sizes of the first packets.

Random Forest combines many decision trees. Each tree learns different rules about the relationship between the traffic features and the label, such as the protocol or the queried domain. The forest then combines the tree predictions. This gives us a strong and interpretable baseline for structured metadata without requiring the features to be converted into images or raw sequences.

We also use **XGBoost** as a comparison model. XGBoost builds boosted decision trees sequentially, with each new tree trying to correct errors made by the previous trees. It is a useful comparison because it is a different tree-based learning strategy, while still working on exactly the same features.

The comparison is fair because both models use the same dataset, the same feature set, the same labels, and the same train-test split. Therefore, if one model performs better, the difference is more likely to come from the learning method rather than from a different data preparation process.

The purpose of using two models is not simply to select the model with the highest score. It is to check whether the observed traffic signal is stable across reasonable machine-learning approaches. If both models identify similar patterns, our conclusion about leakage is stronger.

## 2. Split Strategy

The second part is the data split.

We use **leave-one-repeat-out cross-validation**. The dataset contains repeated captures of the same domains and protocols. For one round, we train on the available repeats and hold out one complete repeat for testing. We then rotate the held-out repeat and repeat the process.

For example, if we have three captures of a domain, we might train using repeats zero and one, and test on repeat two. In the next round, a different repeat becomes the test set.

This is important because repeated captures can be very similar. If one capture from the same repeated run appears in the training set and another almost identical capture appears in the test set, the model may memorize the recording conditions instead of learning a general traffic fingerprint. That would produce an artificially high score.

By holding out one entire repeat, we keep repeated or near-duplicate captures separated between training and testing. The test data therefore represents a new observation of the same experimental conditions rather than a copy of a training example.

This split also matches the research question. We want to know whether an attacker can recognize a protocol or domain from a new capture, not whether a model can recognize a trace that is almost identical to one it has already seen.

## 3. Significance Test

The third part is the significance test.

A classifier can produce an accuracy value even when there is no meaningful relationship between the features and the labels. To measure whether the observed accuracy is real, we create a null baseline using **100 label permutations**.

In each permutation, the traffic features stay exactly the same, but the labels are randomly shuffled. The model is then trained and evaluated on these incorrect labels. Because the labels no longer correspond to the traffic, these runs estimate the accuracy we could obtain by chance under the same data size, model, and evaluation procedure.

The 100 permutation results form a null distribution. We take the 95th percentile of that distribution as a conservative threshold. We call the leakage evidence supported only when the real-label accuracy is higher than this 95th-percentile baseline.

This test is stronger than comparing accuracy only with a simple chance value. For example, in a perfectly balanced 50-class problem, the theoretical chance level might be two percent. But the actual dataset may be imbalanced, repeated, or affected by the split structure. The permutation baseline captures those practical effects.

The interpretation is straightforward: if the real labels do not beat the permutation threshold, we should not claim that the model found a reliable fingerprint. A low score or a score close to the shuffled-label baseline is treated as noise rather than evidence of privacy leakage.

## 4. Metrics Reported

The final part is the set of metrics.

First, we report **Top-1 accuracy**. This is the percentage of test flows for which the model's first prediction is correct. It answers the strict question: did the model identify the exact protocol or domain?

We also report **Top-5 accuracy**. Here, the prediction is counted as successful if the correct label appears anywhere among the model's five most likely labels. This is useful for fingerprinting because an attacker may not need one certain answer. Narrowing the possibilities to five candidates can still reveal substantial information.

Next, we report **macro-F1**. F1 combines precision and recall. The macro version calculates the F1-score separately for each class and then gives every class equal weight. This prevents common classes from hiding poor performance on less frequent classes.

We report **95 percent Wilson confidence intervals** for accuracy. A single accuracy value is only an estimate from a finite test set. The confidence interval shows the range of values reasonably compatible with the observed data. Narrow intervals indicate a more precise estimate, while wider intervals indicate more uncertainty.

Finally, we report a **chance-adjusted resistance score**. This helps interpret privacy performance relative to the relevant chance level. A fingerprinting accuracy close to chance suggests stronger resistance, while accuracy substantially above chance indicates that the traffic contains usable identifying information.

It is important to remember that the direction depends on the metric. For an attacker, higher classification accuracy is better. For privacy, lower accuracy is better. Therefore, when we describe a protocol as more resistant, we mean that the attacker performs closer to chance.

## Closing Summary

To summarize the methodology:

1. Random Forest is the primary model for tabular traffic features, and XGBoost provides an independent comparison.
2. Leave-one-repeat-out validation prevents repeated captures from leaking between training and testing.
3. One hundred label permutations create a practical chance baseline, and leakage is accepted only when the real result exceeds its 95th percentile.
4. Top-1, Top-5, macro-F1, confidence intervals, and chance-adjusted resistance together describe both attack performance and statistical reliability.

This methodology ensures that any reported leakage is not simply an artifact of duplicated captures, class imbalance, or random chance. It gives us a more credible comparison of how much privacy each encrypted DNS protocol provides.

Thank you.
