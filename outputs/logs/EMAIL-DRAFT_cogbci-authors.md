# Email draft — COG-BCI dataset authors

**Before sending, fill in:** `[YOUR NAME]`, `[YOUR AFFILIATION / STATUS]`,
and optionally `[REPO URL]`. Nothing else needs editing.

**To:** the corresponding author of Hinss, Jahanpour, Somon, Pluchon, Dehais &
Roy (2023), *Scientific Data* 10:85 — the address is on the paper's first page.
Consider cc'ing R. N. Roy and F. Dehais, who are the senior authors on both the
dataset paper and the analyses being reproduced.

**Attach or link:** nothing on the first email. Offer, don't send.

---

**Subject:** Reproducing the COG-BCI baseline — four questions about the dataset revision and the EEG analysis

Dear Dr [LAST NAME],

I am [YOUR NAME], [YOUR AFFILIATION / STATUS]. I am running an independent
reproduction and extension of the COG-BCI analyses as a methodological study on
whether task-difficulty labels are valid targets for passive BCI workload
decoding. Thank you for releasing the dataset so completely — the trigger list,
the notebook file with per-session task order, and the per-condition behavioural
outputs have all been directly useful.

The reproduction has gone well. The manipulation checks replicate closely: my
RSME × difficulty F values agree with the published ones to four significant
figures for both N-Back and MATB, and the MATB EEG results reproduce including
the increase in posterior alpha with difficulty.

Four things I cannot resolve from the paper, and I would rather ask than guess.

**1. Is the current Zenodo release the same revision that the published
analyses used?** Several details differ from what I expected:

- the ECG channel is named `ECG1`; I find no `TP9` in any of the 87 sessions
- the full extraction is 35.89 GB
- 27 of the 29 subject archives contain an extra directory level that the other
  two do not

Individually these are cosmetic, but together they made me wonder whether the
record was updated after the analyses were run.

**2. How was band power computed for the task comparisons?** Specifically,
absolute power, power relative to total broadband power, or power normalised to
the resting-state recordings? And which electrodes made up the "frontal" and
"posterior" ROIs? I have used absolute log power over a full-montage ROI, and
this is the choice I am least confident matches yours.

**3. N-Back trial pacing.** The documented inter-trial interval is 2.0 s, but
the median interval I measure from the triggers is 2.516 s in session 1, falling
to 2.008 s by session 3. Per-session N-Back accuracy tracks this pacing closely
in my data (Spearman r = 0.946). Was the timing adjusted between sessions, or is
this more likely something in how I am reading the trigger stream?

**4. The bad-channel criterion.** The paper gives a 2 SD threshold and reports
about 0.34 interpolated channels per task. On a 62-channel montage I cannot get
those two numbers to agree under any statistic I have tried — 2 SD gives far
more channels than that. Was the threshold applied to a different statistic, or
after a different reference or filtering step?

Question 2 is the one that matters most to me. I reproduce the published null
for N-Back **theta**, but I find that N-Back **alpha** decreases monotonically
with difficulty (posterior η²ₚ = 0.36; 27 of 29 subjects individually show
2-back below 0-back), where the paper reports no effect. I have checked the
obvious explanations on my side — the effect is stable across three epoch
rejection thresholds and two ROI definitions, it survives adjusting for
presentation order, and task order is counterbalanced in the notebook file so
time-on-task cannot confound it. That leaves a difference in how power itself
was quantified as the most likely remaining explanation, which is why I ask.

I am not writing to dispute the published result — much more likely I am doing
something differently, and a one-line answer to question 2 may well settle it.

Happy to share my analysis code, the preprocessing configuration, or the
intermediate tables if any of that would be useful to you. [Everything is at
REPO URL.] And if it would be more efficient to talk this through, I am glad to
arrange a short call at your convenience.

Thank you for your time, and for the dataset.

Best regards,
[YOUR NAME]
[email / affiliation line]

---

## Why the email is shaped this way

**Credibility before questions.** The second paragraph reports what *worked*,
with a number that is checkable (four significant figures). An email that opens
with a non-replication reads as a complaint; one that opens with a successful
reproduction reads as a colleague.

**The hard question is fourth, not first.** Questions 1, 3 and 4 are cheap for
them to answer and establish that the queries are specific and well-founded.
The alpha non-replication comes after, framed as a probable difference on our
side — which is the honest position, since it genuinely may be.

**It is disclosed rather than hidden.** They will find out eventually; learning
it from us first is both correct and strategically better. The framing states a
measured fact and an explicit list of what has already been ruled out, so it
cannot be answered with "did you check the order?".

**One ask is marked as primary.** Busy people answer the question you tell them
matters. If only question 2 comes back, the email has still done its job.

**No attachments on first contact**, and the call is offered, not requested.

## If there is no reply in three weeks

Send one short follow-up to the same thread, asking only question 2. If that
also goes unanswered, path 6.3 in the mentor briefing — testing the effect in
the Neuroergonomics 2021 dataset from the same group — answers the underlying
question without them.
