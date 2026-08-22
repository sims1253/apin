// W-34 arm B: hier_2pl with the likelihood line reformulated as ONE var-mode
// GEMM over the complete J x I response grid (verified: data is the full grid,
// item-major). Identical math; eta[j,i] = alpha_i*(theta_j - beta_i) computed
// as [theta, -1](Jx2) %*% [alpha; alpha.*beta](2xI). to_vector (column-major)
// reproduces the stock observation order exactly.
data {
  int<lower=1> I; // # items
  int<lower=1> J; // # persons
  int<lower=1> N; // # observations (= J*I for this dataset)
  array[N] int<lower=1, upper=I> ii; // item for n (unused in likelihood; kept for identical data)
  array[N] int<lower=1, upper=J> jj; // person for n (unused in likelihood)
  array[N] int<lower=0, upper=1> y; // correctness for n
}
parameters {
  vector[J] theta; // abilities
  vector[I] xi1;
  vector[I] xi2;
  vector[2] mu; // vector for alpha/beta means
  vector<lower=0>[2] tau; // vector for alpha/beta residual sds
  cholesky_factor_corr[2] L_Omega;
}
transformed parameters {
  vector[I] alpha;
  vector[I] beta;
  array[I] vector[2] xi; // alpha/beta pair vectors
  for (i in 1 : I) {
    xi[i, 1] = xi1[i];
    xi[i, 2] = xi2[i];
    alpha[i] = exp(xi[i, 1]);
    beta[i] = xi[i, 2];
  }
}
model {
  matrix[2, 2] L_Sigma;
  matrix[J, I] eta = append_col(theta, rep_vector(-1.0, J))
                     * append_row(to_row_vector(alpha),
                                  to_row_vector(alpha .* beta));
  L_Sigma = diag_pre_multiply(tau, L_Omega);
  for (i in 1 : I) {
    target += multi_normal_cholesky_lpdf(xi[i] | mu, L_Sigma);
  }
  theta ~ normal(0, 1);
  L_Omega ~ lkj_corr_cholesky(4);
  mu[1] ~ normal(0, 1);
  tau[1] ~ exponential(.1);
  mu[2] ~ normal(0, 5);
  tau[2] ~ exponential(.1);
  target += bernoulli_logit_lpmf(y | to_vector(eta));
}
generated quantities {
  corr_matrix[2] Omega;
  Omega = multiply_lower_tri_self_transpose(L_Omega);
}
