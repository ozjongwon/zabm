# Evaluation evidence reconciliation v1

Status: proposed, pending maintainer verification.

Source pack: `2026-11-23.3-frozen-1`.

This audit checks evaluation items 001-008 in the
`conflicting_evidence` category and compatibility items 012-015 against
the frozen manufacturer PDFs. It does not change the source pack or
evaluation expectations.

## Source findings

### RockShox Reba top cap

`sram-rockshox-reba-2011-technical-manual`, physical and printed page 7,
section `TORQUE TIGHTENING VALUES`, contains:

> Top Cap 7.3 N·m (65 in-lb)
>
> Top Cap (Air U-Turn Only) 14.6 N·m (130 in-lb)

The expected conflict for `conflict-001` through `conflict-004` is
supported when the fork variant is not identified. Proposed verified
specifications:

- `sram-rockshox-reba-top-cap-torque`: `7.3 N·m (65 in-lb)`, with
  conditions `Fork: 2011 RockShox Reba` and
  `Variant: top cap other than Air U-Turn`.
- `sram-rockshox-reba-top-cap-air-uturn-torque`: `14.6 N·m (130 in-lb)`,
  with conditions `Fork: 2011 RockShox Reba` and
  `Variant: Air U-Turn only`.

### Reverb Stealth hose barb

`sram-rockshox-reverb-hose-replacement-rev-c`, physical and printed
page 12, section `Hose Barb and Barb Sleeve Preparation`, contains:

> Tighten the hose barb and barb sleeve.
>
> 7 mm 1.1-2.2 N•m (10-20 in-lb)

The same document, physical and printed page 16, section
`Reverb™ Stealth Hose Removal and Installation`, contains:

> Hose Barb with Barb Sleeve: Install the new hose barb into the
> seatpost and tighten.
>
> 10 mm 3.4-4.5 N•m (30-40 in-lb)

These values apply to different joints. They do not establish that one
fastener has conflicting values. Proposed action:

- Add verified specifications for `hose barb and barb sleeve assembly`
  at the page-12 value and `hose barb into seatpost` at the page-16
  value.
- Change `conflict-005` through `conflict-008` to
  `clarification_required`, because the questions do not identify
  which joint they mean.

### Reverb AXS saddle rails

`sram-rockshox-reverb-axs-user-manual-rev-l`, physical and printed page
13, section `Compatibility Compatibilité Compatibilidade`, contains:

> Reverb AXS seatposts are compatible with saddles with metal 7 mm
> diameter rails and composite 7x9 mm oval rails, and composite 7x10 mm
> oval rails when used with optionally available clamps.

The expected compatibility outcomes for `compat-012` and `compat-013`
are explicitly supported. Proposed verified rule:

- `sram-reverb-axs-composite-7x9-saddle-rails`: Reverb AXS seatpost and
  saddle with composite 7x9 mm oval rails, outcome `compatible`, with
  conditions `Seatpost: Reverb AXS` and
  `Saddle rail profile: composite 7x9 mm oval`.

### Reverb AXS seatpost and seat tube diameter

The same page contains:

> Reverb AXS is available in 30.9 mm, 31.6 mm, and 34.9 mm diameters.
>
> Seatpost and seat tube diameters must be the same.

The expected outcomes for `compat-014` and `compat-015` are supported by
an explicit manufacturer requirement. A verified `not_compatible` rule
is proposed for a Reverb AXS seatpost paired with a seat tube of a
different diameter, with conditions recording the available seatpost
diameters and the equality requirement.

## Item disposition

| Item | Source-supported? | Proposed disposition |
| --- | --- | --- |
| `conflict-001` | Yes | Keep `conflicting_evidence`; add the two Reba specifications. |
| `conflict-002` | Yes | Keep `conflicting_evidence`; add the two Reba specifications. |
| `conflict-003` | Yes | Keep `conflicting_evidence`; add the two Reba specifications. |
| `conflict-004` | Yes | Keep `conflicting_evidence`; add the two Reba specifications. |
| `conflict-005` | No, not as a conflict | Add both joint-specific specifications; change to `clarification_required`. |
| `conflict-006` | No, not as a conflict | Add both joint-specific specifications; change to `clarification_required`. |
| `conflict-007` | No, not as a conflict | Add both joint-specific specifications; change to `clarification_required`. |
| `conflict-008` | No, not as a conflict | Add both joint-specific specifications; change to `clarification_required`. |
| `compat-012` | Yes | Add the composite 7x9 mm rail rule. |
| `compat-013` | Yes | Add the composite 7x9 mm rail rule. |
| `compat-014` | Yes | Add an explicit mismatched-diameter rule. |
| `compat-015` | Yes | Add an explicit mismatched-diameter rule. |

## Required maintainer review

For every new verified specification and compatibility rule, confirm:

- the quoted excerpt matches the frozen PDF;
- the component and attribute vocabulary is correct;
- applicability conditions preserve the source distinction;
- `verified_by` and `verified_at` identify this review.

After approval, regenerate the source-derived evidence, update the
evaluation labels, create a replacement evaluation freeze, and run
source validation, retrieval smoke, and the complete evaluation.
