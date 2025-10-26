// SEIR model with time-varying transmission rate for COVID-19
// Based on: https://mc-stan.org/learn-stan/case-studies/boarding_school_case_study.html

functions {
  // SEIR ODE system
  vector seir_ode(real t, vector y, real beta, real sigma, real gamma, real N) {
    vector[4] dydt;
    real S = y[1];
    real E = y[2];
    real I = y[3];
    real R = y[4];
    
    real infection_rate = beta * S * I / N;
    
    dydt[1] = -infection_rate;                    // dS/dt
    dydt[2] = infection_rate - sigma * E;         // dE/dt
    dydt[3] = sigma * E - gamma * I;              // dI/dt
    dydt[4] = gamma * I;                          // dR/dt
    
    return dydt;
  }
}

data {
  int<lower=1> n_days;                    // Number of days
  real t0;                                 // Initial time
  array[n_days] real ts;                   // Time points
  int<lower=0> N;                          // Population size
  array[4] real y0;                        // Initial conditions [S, E, I, R]
  array[n_days] int<lower=0> cases;        // Observed daily cases
  
  // Priors (optional, can be set from data)
  real<lower=0> beta_mean;
  real<lower=0> beta_sd;
  real<lower=0> sigma_mean;
  real<lower=0> sigma_sd;
  real<lower=0> gamma_mean;
  real<lower=0> gamma_sd;
}

transformed data {
  real x_r[0];  // No real data to pass to ODE
  int x_i[0];   // No integer data to pass to ODE
}

parameters {
  real<lower=0> beta;              // Transmission rate
  real<lower=0> sigma;             // Incubation rate (1/latent period)
  real<lower=0> gamma;             // Recovery rate (1/infectious period)
  real<lower=0> phi_inv;           // Overdispersion parameter
  real<lower=0> i0;                // Initial infected (if unknown)
}

transformed parameters {
  array[n_days] vector[4] y;       // Solution from ODE solver
  real phi = 1.0 / phi_inv;
  vector[n_days] pred_cases;
  
  // Solve ODE
  {
    array[4] real y0_adjusted = y0;
    y0_adjusted[3] = i0;  // Use estimated initial infections
    y0_adjusted[1] = N - i0;  // Adjust susceptibles
    
    y = ode_rk45(seir_ode, y0_adjusted, t0, ts, beta, sigma, gamma, N);
  }
  
  // Calculate daily incidence (new cases per day)
  for (i in 1:n_days) {
    pred_cases[i] = sigma * y[i][2];  // New cases = rate of leaving E compartment
  }
}

model {
  // Priors
  beta ~ normal(beta_mean, beta_sd);
  sigma ~ normal(sigma_mean, sigma_sd);
  gamma ~ normal(gamma_mean, gamma_sd);
  phi_inv ~ exponential(5);
  i0 ~ exponential(1.0 / 10);  // Prior on initial infections
  
  // Likelihood - negative binomial for overdispersed count data
  for (i in 1:n_days) {
    if (pred_cases[i] > 0) {
      cases[i] ~ neg_binomial_2(pred_cases[i], phi);
    }
  }
}

generated quantities {
  real R0 = beta / gamma;                    // Basic reproduction number
  real latent_period = 1.0 / sigma;          // Days in latent period
  real infectious_period = 1.0 / gamma;      // Days infectious
  
  // Posterior predictive samples
  array[n_days] int pred_cases_samples;
  for (i in 1:n_days) {
    if (pred_cases[i] > 0) {
      pred_cases_samples[i] = neg_binomial_2_rng(pred_cases[i], phi);
    } else {
      pred_cases_samples[i] = 0;
    }
  }
  
  // Log likelihood for model comparison
  real log_lik = 0;
  for (i in 1:n_days) {
    if (pred_cases[i] > 0) {
      log_lik += neg_binomial_2_lpmf(cases[i] | pred_cases[i], phi);
    }
  }
}
