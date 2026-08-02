# Baseline evaluation

## Evaluation contract

The rules baseline receives only `complaint_type` and `descriptor`. The
existing `category` is retained as ground truth and is never included in the
classifier input. `resolution_description` is also excluded. Evaluation runs
on `nyc311_validation.json`; `nyc311_test.json` remains reserved for final
evaluation.

The current labels are weak labels generated from exact reviewed pairs in
`complaint_mapping.json`. Consequently, validation primarily checks whether
the implementation reproduces the declared taxonomy. It does not independently
measure semantic generalization.

## Taxonomy correction

Mapping version 3.0.0 restricts `flooding` to descriptors that explicitly
indicate flooding, ponding, or overflow. Sewer backups, clogged drains or catch
basins without explicit flooding, defective catch basins, and routine sewer
maintenance fall back to `unknown`.

Rules version 2 removes generic clogged-drain and catch-basin signals and keeps
explicit flooding, ponding, and overflow signals.

## Results

| Version | Validation accuracy | Macro-F1 | Main finding |
| --- | ---: | ---: | --- |
| rules-v1 / mapping-v2 | 0.8967 | 0.8893 | 31 sewer-only weak labels were missed as flooding |
| rules-v2 / mapping-v3 | 1.0000 | 1.0000 | Rules agree with the corrected weak-label boundary |

The perfect rules-v2 score must not be presented as final model performance.
Before comparing learned models, create a manually reviewed, stratified gold
set with ambiguous examples and report agreement between reviewers. The final
test split must not be used while rules or models are being tuned.

## Gold-set candidate pool

`nyc311_gold_test.json` contains 250 records, balanced at 50 examples for each
canonical category and isolated from all train, validation, and test splits.
The unknown class deliberately includes 20 sewer-only boundary cases and 30
diverse out-of-scope complaints. Flooding includes explicit flooding, ponding,
and overflow descriptors. The fallen-tree class contains real NYC 311 fallen
tree records with an explicitly marked synthetic road-obstruction clause in
`evaluation_description`; these cases test category precedence. Review status
is tracked in the manifest rather than repeated on every record. The file
becomes a true gold set only after manual review is completed.

The approved gold set was evaluated once against the frozen rules-v2 baseline
on 2026-08-01. It achieved 0.9800 accuracy and 0.9799 macro-F1. All explicit
flooding, fallen-tree-versus-road-obstruction, sewer-only, and out-of-scope
unknown boundary cases were correct. Five `Street Condition / Unsafe Worksite`
records labeled `road_obstruction` were predicted as `unknown`. These errors
are documented findings; rules-v2 must not be tuned against this gold set.
