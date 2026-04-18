# Extraction Template — What to Pull from Raw Evidence

Raw evidence captures are long (often 1000+ lines). The goal of distillation is to produce a page that answers seven questions, and nothing more. Read the evidence with these questions in hand.

## 1. Problem

What concrete problem does the paper target? State it in one sentence, with the constraint that makes it non-trivial. Avoid vague framings like "improving X" — pin down the constraint, the regime, or the metric that the paper actually moves.

Example: "Robot manipulation policies trained on one embodiment rarely transfer to new arms without fine-tuning, even when the pretraining dataset is large."

## 2. Core Idea

What is the paper's proposal in one technical sentence? The mechanism, not the slogan. If you need to explain the proposal, you are not done extracting it yet.

Example: "Discretize continuous robot actions into tokens and fine-tune a vision-language model to emit those tokens from image and instruction inputs."

## 3. Contributions

Bulleted list. Three to five items. Each item should be a specific claim the paper makes — a dataset released, a training recipe shown to work, a benchmark beaten, a negative result demonstrated. Avoid restating the abstract; pull the contributions from the paper's own "contributions" section or from the evaluation.

## 4. Data and Setup

What did the paper train on, and what did it evaluate on? Quantities matter: number of demonstrations, number of tasks, number of episodes, number of robots. This is the section future agents will use to judge whether a claim is load-bearing.

## 5. Results

The headline numbers, with the comparison. Not "state of the art" — the actual delta against the best prior method, on the specific benchmark. If the paper has multiple benchmarks, pick the two most load-bearing. Include honest caveats when the gain is small or the comparison is not apples-to-apples.

## 6. Novelty

Why is this paper not redundant with the three closest prior works? Name the prior works, state the delta. If the novelty is "scale" or "engineering", say so — do not inflate a scaling paper into a conceptual one.

## 7. Limitations

What does the paper fail at, or refuse to claim? Pull from the paper's own limitations section when honest; augment with your read of what the method cannot address. This is the section that makes the page useful months later.

## Optional: Relations

Cross-links to vault papers that share this paper's concepts, compete with it, or are built on top of it. One-line each, with the concrete connection. Skip if no strong relation exists.

## Optional: Impact

A short paragraph on why this paper matters beyond its own numbers. Include only if the impact is explicit in the literature or obvious from the evidence. Speculative impact statements hurt page quality.
