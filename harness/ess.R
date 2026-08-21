#!/usr/bin/env Rscript
# Rank-normalized ESS/R-hat (Vehtari et al. 2021) for one config dir of chain CSVs.
# usage: Rscript ess.R <dir-with-chain_csvs> <out.json>
suppressMessages({library(posterior); library(jsonlite)})
args <- commandArgs(trailingOnly = TRUE)
dir_in <- args[1]; out_json <- args[2]
files <- sort(list.files(dir_in, pattern = "^chain_[0-9]+\\.csv$", full.names = TRUE))
stopifnot(length(files) > 0)

drops <- c("lp__","accept_stat__","stepsize__","treedepth__","n_leapfrog__",
           "divergent__","energy__","X")
dfs <- lapply(files, function(f) read.csv(f, comment.char = "#"))
keep <- setdiff(names(dfs[[1]]), drops)
n_draws <- nrow(dfs[[1]]); n_chains <- length(dfs)
arr <- array(NA, dim = c(n_draws, n_chains, length(keep)))
for (ch in seq_len(n_chains)) arr[, ch, ] <- as.matrix(dfs[[ch]][, keep, drop = FALSE])
dimnames(arr) <- list(NULL, NULL, keep)
d <- as_draws_df(arr)

s <- summarise_draws(d, "ess_bulk", "ess_tail", "rhat")
eb <- s$ess_bulk; et <- s$ess_tail; rh <- s$rhat
names(eb) <- s$variable; names(et) <- s$variable; names(rh) <- s$variable
ok <- is.finite(eb)
geomean <- function(x) exp(mean(log(pmax(x[x > 0], 1e-12))))
out <- list(
  ess_bulk_min = min(eb[ok]), ess_bulk_geomean = geomean(eb[ok]),
  ess_tail_min = min(et[is.finite(et)]), rhat_max = max(rh[is.finite(rh)]),
  n_params = sum(ok), n_chains = n_chains, n_draws = n_draws,
  worst_params = names(sort(eb[ok]))[1:min(5, sum(ok))],
  ess_bulk_per_param = as.list(stats::setNames(round(eb[ok], 1), names(eb)[ok]))
)
write(toJSON(out, auto_unbox = TRUE, digits = 6), out_json)
cat(sprintf("ess_bulk min=%.0f geomean=%.0f rhat_max=%.4f -> %s\n",
            out$ess_bulk_min, out$ess_bulk_geomean, out$rhat_max, out_json))
