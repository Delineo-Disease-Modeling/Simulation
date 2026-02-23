# Stan Use Cases for Delineo (Meeting Overview)

## 1. Calibrating Delineo to Real-World Data

- **What we do**  
  Use Stan to fit a simple SEIR epidemic model to real county case data.

- **Why this matters**  
  - Gives us *baseline epidemiological parameters* (e.g., R₀, infectious period) with **credible intervals**.  
  - Provides a "ground-truth" population-level model to compare Delineo against.

- **Impact for Delineo**  
  - Demonstrates that Delineo is anchored to real data, not just hand-tuned.  
  - Lets us say: *"Delineo’s effective R₀ and trajectory line up with a rigorously calibrated Bayesian model."*

---

## 2. Validating Delineo’s Epidemic Trajectories

- **What we do**  
  - Generate predictions from the Stan SEIR model (posterior predictive).  
  - Compare Delineo’s simulated case curves to Stan’s 95% credible intervals.

- **Why this matters**  
  - Answers the question: *"Does the agent-based simulator behave like a reasonable epidemic model?"*  
  - Quantifies agreement instead of relying on eyeballing plots.

- **Impact for Delineo**  
  - If Delineo mostly stays inside Stan’s uncertainty bands and tracks the same peaks/timing, we can report:  
    - **Coverage**: % of Delineo points inside Stan’s 95% CI.  
    - **Correlation**: How similar the trajectories are.  
  - This becomes an easy story in the meeting: *"Our simulator reproduces standard SEIR behavior under realistic assumptions."*

---

## 3. Testing Policy and Scenario Assumptions

- **What we do**  
  - Use Stan models with time-varying transmission (e.g., `seir_interventions.stan`) to represent interventions like school closures or mobility reductions.  
  - Compare these intervention effects to what Delineo produces when we flip the same policy switches.

- **Why this matters**  
  - Checks whether Delineo’s policy levers (lockdowns, NPIs, etc.) have **realistic magnitude and timing** of impact.  
  - Helps identify if Delineo over- or under-reacts to a given policy change.

- **Impact for Delineo**  
  - Lets us say: *"When we impose intervention X in Delineo, the resulting change in transmission is consistent with what a calibrated Stan model predicts."*  
  - Builds confidence that our policy scenarios are not just visually plausible but quantitatively grounded.

---

## 4. Communicating Uncertainty to Stakeholders

- **What we do**  
  - Stan provides full posterior distributions and prediction intervals.  
  - We overlay Delineo outputs on top of these intervals.

- **Why this matters**  
  - Frames results in terms of **ranges** instead of single-point forecasts.  
  - Makes it easy to explain uncertainty to non-technical audiences: *"These shaded bands show what is plausible; our simulator stays inside them."*

- **Impact for Delineo**  
  - Positions Delineo as a tool that **embraces uncertainty** rather than hiding it.  
  - Supports more responsible decision-making narratives in your meeting.

---

## 5. Using Stan Results to Improve Delineo

- **What we do**  
  - Compare Stan’s parameter estimates (e.g., R₀, latent and infectious periods) against the implicit parameters in Delineo.  
  - Use mismatches to guide tuning or model refinement.

- **Why this matters**  
  - Turns Stan into a **diagnostic tool**: if Delineo needs unrealistic parameters to match data, that’s a signal to inspect model structure.  
  - Helps prioritize which parts of the simulator to calibrate or redesign.

- **Impact for Delineo**  
  - Clear path to continued improvement: *"We use Stan to systematically calibrate and stress-test Delineo, not just to validate once and walk away."*  
  - Gives you concrete next steps to mention in your update (multi-county fits, more complex Stan models, etc.).

---

## How to Present This in the Meeting

You can summarize the above in three short points:

1. **Calibration** – Stan gives us rigorously estimated epidemic parameters from real data.  
2. **Validation** – We check that Delineo’s trajectories and policy responses agree with a trusted Bayesian model.  
3. **Improvement Loop** – Differences between Stan and Delineo tell us where to tune and extend the simulator.
