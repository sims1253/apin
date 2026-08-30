#include <stdio.h>
#include <math.h>
int main() {
  double c[5] = {0.0, 0.95904659396029357, -0.86871720078685277, -1.5597403778588137, -1.7171484285464214};
  double mx = c[0];
  for (int k = 1; k < 5; ++k) if (c[k] > mx) mx = c[k];
  double e[5]; for (int k = 0; k < 5; ++k) e[k] = exp(c[k] - mx);
  // S sequential
  double S1 = 0; for (int k = 0; k < 5; ++k) S1 = S1 + e[k];
  // S packet-like: predux4 then + tail: (e0+e1+e2+e3 pairwise?) two orders:
  double S2 = (e[0]+e[1]) + (e[2]+e[3]); S2 = S2 + e[4];           // pairwise
  double S3 = ((e[0]+e[1])+e[2])+e[3]; S3 = S3 + e[4];               // seq4 then tail
  printf("S1=%.17g S2=%.17g S3=%.17g\n", S1, S2, S3);
  double target = 0.22632293691309968; // eigen p[0]
  double man    = 0.22632293691309965; // manual p[0]
  printf("div S1: %.17g\n", e[0]/S1);
  printf("div S2: %.17g\n", e[0]/S2);
  printf("div S3: %.17g\n", e[0]/S3);
  printf("recip S1: %.17g\n", e[0]*(1.0/S1));
  printf("recip S2: %.17g\n", e[0]*(1.0/S2));
  printf("target=%.17g man=%.17g\n", target, man);
  return 0;
}
