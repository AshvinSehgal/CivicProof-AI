# CivicProof incident taxonomy

The MVP uses five mutually exclusive labels. NYC 311 records are assigned by
an exact `complaint_type` and `descriptor` pair from
`complaint_mapping.json`. Unmatched records must remain `unknown`.

## `pothole`

A road-surface cavity explicitly reported as a pothole. Other street defects,
cave-ins, plate conditions, and general wear are excluded.

## `fallen_tree`

A fallen or imminently falling public tree or limb, including uprooted trees,
split trunks, and cracked branches expected to fall. General pruning, healthy
overgrowth, dead-tree requests, and illegal tree damage are excluded.

## `flooding`

An explicit report of street or highway flooding, ponding, or overflowing
water. A record may originate from a sewer-related NYC 311 complaint type, but
its descriptor must explicitly indicate flooding, ponding, or overflow. Sewer
backups, clogged drains or catch basins without explicit flooding, defective
catch basins, odors, damaged covers, and routine sewer maintenance are
excluded.

## `road_obstruction`

A physical obstruction in the public right of way, including construction
blockages, dumped material, objects, or vegetation blocking a street or
traffic control device. Parking and law-enforcement complaints are excluded.

## `unknown`

Any record that does not match an exact reviewed pair. `unknown` is an
intentional abstention category, not a place for guessed labels.
