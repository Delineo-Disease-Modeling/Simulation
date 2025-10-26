// SEIR model with time-varying transmission rate (interventions)
// Allows beta to change at specified intervention times

functions {
  // SEIR ODE system with time-varying beta
  vector seir_ode(real t, vector y, real beta, real sigma, real gamma, real N) {
    vector[4] dydt;
    real S = y[1];
    real E = y[2];
    real I = y[3];
    real R = y[4];
    
    real infection_rate = beta * S * I / N;
    
    dydt[1] = -infection_rate;
    dydt[2] = infection_rate - sigma * E;
    dydt[3] = sigma * E - gamma * I;
    dydt[4] = gamma * I;
    
    return dydt;
  }
}

data {
  int<lower=1> n_days;
  real t0;
  array[n_days] real ts;
  int<lower=0> N;
  array[4] real y0;
  array[n_days] int<lower=0> cases;
  
  // Intervention structure
  int<lower=1> n_periods;                      // Number of time periods
  array[n_periods] int<lower=1> period_ends;   // Day indices where periods end
  
  // Priors
  real<lower=0> beta_mean;
  real<lower=0> beta_sd;
  real<lower=0> sigma_mean;
  real<lower=0> sigma_sd;
  real<lower=0> gamma_mean;
  real<lower=0> gamma_sd;
}

parameters {
  vector<lower=0>[n_periods] beta;     // Transmission rate per period
  real<lower=0> sigma;
  real<lower=0> gamma;
  real<lower=0> phi_inv;
  real<lower=0> i0;
}

transformed parameters {
  array[n_days] vector[4] y;
  real phi = 1.0 / phi_inv;
  vector[n_days] pred_cases;
  
  // Solve ODE piecewise for each intervention period
  {
    array[4] real y_init = y0;
    y_init[3] = i0;
    y_init[1] = N - i0;
    
    int start_idx = 1;
    for (p in 1:n_periods) {
      int end_idx = period_ends[p];
      array[end_idx - start_idx + 1] real ts_segment;
      
      for (i in start_idx:end_idx) {
        ts_segment[i - start_idx + 1] = ts[i];
      }
      
      array[end_idx - start_idx + 1] vector[4] y_segment;
      y_segment = ode_rk45(seir_ode, y_init, 
                           start_idx == 1 ? t0 : ts[start_idx - 1], 
                           ts_segment, beta[p], sigma, gamma, N);
      
      for (i in start_idx:end_idx) {
        y[i] = y_segment[i - start_idx + 1];
      }
      
      if (p < n_periods) {
        y_init = to_array_1d(y[end_idx]);
      }
      
      start_idx = end_idx + 1;
    }
  }
  
  for (i in 1:n_days) {
    pred_cases[i] = sigma * y[i][2];
  }
}

model {
  // Priors
  for (p in 1:n_periods) {
    beta[p] ~ normal(beta_mean, beta_sd);
  }
  sigma ~ normal(sigma_mean, sigma_sd);
  gamma ~ normal(gamma_mean, gamma_sd);
  phi_inv ~ exponential(5);
  i0 ~ exponential(1.0 / 10);
  
  // Likelihood
  for (i in 1:n_days) {
    if (pred_cases[i] > 0) {
      cases[i] ~ neg_binomial_2(pred_cases[i], phi);
    }
  }
}

generated quantities {
  vector[n_periods] R0;
  real latent_period = 1.0 / sigma;
  real infectious_period = 1.0 / gamma;
  
  for (p in 1:n_periods) {
    R0[p] = beta[p] / gamma;
  }
  
  array[n_days] int pred_cases_samples;
  for (i in 1:n_days) {
    if (pred_cases[i] > 0) {
      pred_cases_samples[i] = neg_binomial_2_rng(pred_cases[i], phi);
    } else {
      pred_cases_samples[i] = 0;
    }
  }
  
  real log_lik = 0;
  for (i in 1:n_days) {
    if (pred_cases[i] > 0) {
      log_lik += neg_binomial_2_lpmf(cases[i] | pred_cases[i], phi);
    }
  }
}
