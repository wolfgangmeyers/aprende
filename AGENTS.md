# Agent Content Rules

Aprende curriculum content must be natural Spanish that a real speaker would actually say
and that a learner would actually use. A phrase can be grammatical and still be bad content
if it is stilted, low-utility, or only exists because a template generated it.

Never generate combinatorial or Cartesian-product permutation content. Do not hand-type
tuple spam such as `[head noun] x [adjective] x [connector] x [tail noun]`, and do not
recreate the same pattern through code generation. Content generation must be done through
subagents: one agent drafts candidate content, and independent reviewer agents check it
before it enters the pipeline.

The target dialect is neutral Latin American Spanish for US English speakers. Avoid
Spain-only or peninsular vocabulary, and also avoid slang or wording that is strongly tied
to one Latin American country when a broadly understood option exists.

All curriculum content must pass all of:

- correctness review: Spanish grammar, translation accuracy, CEFR fit, and exercise quality
- naturalness/authenticity review: a native-speaker or language-teacher lens asking whether a
  real speaker would say it and whether it is useful for learners
- dialect-consistency review: neutral Latin American Spanish, with no peninsular-only or
  hyper-regional wording

These are separate dimensions. New or AI-assisted curriculum content needs at least two
independent approved reviews, and phrase/chunk content must not be accepted unless the
naturalness/authenticity and dialect-consistency dimensions pass.

Cautionary example: on 2026-06-02, packs `AI_ACCELERATED_PACK_A2_042` through
`AI_ACCELERATED_PACK_A2_069` were identified as permutation spam. They produced thousands
of grammatically valid but unnatural phrases such as fixed head/adjective fragments paired
with repeated connector-tail lists. That incident is the standard failure mode to avoid:
do not optimize for count, coverage, or mechanical variety at the expense of authentic,
learner-useful Spanish.
