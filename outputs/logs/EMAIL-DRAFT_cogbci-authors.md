# Email to the COG-BCI authors — ready to send

## Addressing

| | | |
|---|---|---|
| **To** | Prof. Raphaëlle N. Roy | `raphaelle.roy@isae.fr` — **verified** on the ISAE-SUPAERO personnel page |
| **Cc** | Prof. Frédéric Dehais | `frederic.dehais@isae.fr` — **not verified**; follows the same institutional pattern as the verified address, but his staff page shows no email. Confirm or drop it. |
| ~~To~~ | Marcel F. Hinss | corresponding author on the paper, but he was a visiting Master's student from Maastricht at the time and almost certainly no longer holds an ISAE address. Do not make him the primary recipient. |

Roy is the right primary recipient: senior author on both the dataset paper and
the analyses being reproduced, permanent faculty, and the person most likely to
know the release history. Attach nothing on first contact.

**Subject:** Reproducing the COG-BCI analyses — which release version did the published analyses use?

---

Dear Professor Roy,

My name is Hongyu Zhou. I am a Master's student in Human Factors at TU Berlin,
and I have become very interested in the validity of the labels used to train
passive BCI workload decoders. I am running an independent reproduction and
extension of the COG-BCI analyses as a methodological study on that question.

Thank you for releasing the dataset so completely. The trigger list, the
notebook file recording per-session task order, and the per-condition
behavioural outputs have all been directly useful — the task-order record in
particular let me rule out a confound that I could not otherwise have addressed.

The reproduction has gone well. My RSME × difficulty F values agree with the
published ones to four significant figures for both N-Back and MATB, and the
MATB EEG results reproduce, including the increase in posterior alpha with
difficulty.

Four questions I cannot resolve from the paper, and I would rather ask than
guess.

**1. Which version of the Zenodo record did the published analyses use, and what
exactly did the version 4 correction change?**

The record notes that "version 4 corrected an electrode name mismatch". I am
working from the concept DOI (10.5281/zenodo.6874128), which resolves to the
latest version, so I have version 4. Two things I would like to be sure of:

- were the analyses reported in the paper run before or after that correction?
- did the correction change only the *label* on the affected channel, or the
  mapping between channel labels and data?

I ask because the reference material I started from describes the ECG channel as
`TP9`, whereas in the copy I have it is `ECG1` — and `TP9` is of course also a
valid EEG electrode name. If an earlier release labelled the cardiac channel
that way, an analysis that treated it as EEG would have carried a cardiac signal
into the montage, and into the average reference. I have no way to tell from
outside whether that is what the correction was about.

**2. How was band power computed for the task comparisons?** Absolute power,
power relative to total broadband power, or power normalised to the
resting-state recordings? And which electrodes made up the "frontal" and
"posterior" ROIs? I have used absolute log power over a full-montage ROI, and
this is the choice I am least confident matches yours.

**3. N-Back trial pacing.** The documented inter-trial interval is 2.0 s, but the
median interval I measure from the triggers is 2.516 s in session 1, falling to
2.008 s by session 3. Per-session N-Back accuracy tracks this pacing closely in
my data (Spearman r = 0.946). Was the timing adjusted between sessions, or is
this more likely something in how I am reading the trigger stream?

**4. The bad-channel criterion.** The paper gives a 2 SD threshold and reports
about 0.34 interpolated channels per task. On a 62-channel montage I cannot make
those two numbers agree under any statistic I have tried — 2 SD gives far more
channels than that. Was the threshold applied to a different statistic, or after
a different reference or filtering step?

Questions 1 and 2 are the ones that matter most to me. I reproduce the published
null for N-Back **theta**, but I find that N-Back **alpha** decreases
monotonically with difficulty (posterior η²ₚ = 0.36; 27 of 29 participants
individually show 2-back below 0-back), where the paper reports no effect.

I have worked through the explanations available on my side. The effect is
stable across three epoch-rejection thresholds and two ROI definitions; it
survives adjustment for presentation position; task order is counterbalanced in
the notebook file, so time-on-task cannot confound it; and ICA and interpolation
are fitted per session across all conditions, so neither can produce a
difference between difficulty levels. MATB reproduces throughout, so it is not
an insensitive pipeline. That leaves either a difference in how power was
quantified, or a difference in the data itself — hence the two questions.

I am not writing to dispute the published result. It is much more likely that I
am doing something differently, and a short answer to either question may well
settle it.

I would be glad to share the analysis code, the preprocessing configuration or
the intermediate tables if any of that would be useful to you, and equally glad
to arrange a short call if that would be more efficient than email.

Thank you for your time, and for the dataset.

Best regards,
Hongyu Zhou
MSc Human Factors, Technische Universität Berlin
zhou.hongyu0219@gmail.com

---

## Why the email is shaped this way

**Credibility before questions.** The third paragraph reports what *worked*, with
a checkable number. An email opening with a non-replication reads as a
complaint; one opening with a successful reproduction reads as a colleague.

**Question 1 is now specific enough to be answered in one line.** The original
draft asked a vague "is this the same revision?". Finding the version-4
changelog turned it into a factual question with a yes/no first half. It also
shows the homework was done, which is most of what earns a reply.

**The TP9 hypothesis is stated as a question, not an accusation.** The mechanism
is laid out so they can confirm or dismiss it immediately, but it is explicitly
framed as something that cannot be determined from outside. If the hypothesis is
wrong, nothing in the email needs retracting.

**The ruled-out list pre-empts the cheap answers.** Order, ICA, interpolation,
thresholds and ROI are all named, so the reply cannot be a suggestion already
tested. This is also the paragraph that signals the work is serious.

**One ask marked as primary.** Busy people answer the question you tell them
matters. If only question 1 comes back, the email has done its job.

**No attachments on first contact.** Sharing is offered, and the call is
offered rather than requested.

## Being a TU Berlin student is worth stating plainly

The PRD's plan was to approach the TU Berlin Neurotechnology chair *after* P1
produced results. P1 is now complete, so that conversation is available
independently of this email — and a reproduction with a documented,
mechanistically explained divergence is a far stronger thing to walk in with
than a proposal.

## If there is no reply in three weeks

Send one short follow-up in the same thread asking only question 1. If that also
goes unanswered, the decisive test does not need them: compare version 1
(10.5281/zenodo.6874129) against version 4 (10.5281/zenodo.7413650) directly —
see the mentor briefing.
