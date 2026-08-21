// Hypothesis: stan::math reverse pass is a pointer-chasing sweep over heap
// chainable nodes -> dependent loads, latency-bound. Compare:
//  (1) sum over contiguous double array (streaming, prefetch-friendly)
//  (2) sum over shuffled linked list of same values (pointer chase)
//  (3) short vector (fits L1) looped — the "hot arena" case
#include <chrono>
#include <cstdio>
#include <random>
#include <vector>
struct Node { double v; Node* next; };
static double now_s(){ static auto t0=std::chrono::steady_clock::now();
  return std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count(); }
int main(){
  const int n = 1<<20;  // 1M nodes ~ 16MB (beyond L2, inside L3)
  std::vector<double> vals(n);
  std::mt19937 rng(7);
  for (auto& v : vals) v = rng() * 1.0 / rng.max();
  // contiguous stream
  { double t0=now_s(); double s=0; for(int r=0;r<40;r++) for(int i=0;i<n;i++) s+=vals[i];
    printf("contiguous stream   : %7.1f ns/M  (s=%.0f)\n", (now_s()-t0)/40*n/1e6*1e6/1e6*1000, s); }
  // shuffled linked list (pointer chase)
  std::vector<Node> nodes(n);
  { std::vector<int> perm(n); for(int i=0;i<n;i++) perm[i]=i;
    for(int i=n-1;i>0;i--){ int j=rng()%(i+1); std::swap(perm[i],perm[j]); }
    for(int i=0;i<n;i++){ nodes[perm[i]].v = vals[i];
                          nodes[perm[i]].next = (i+1<n)? &nodes[perm[i+1]] : nullptr; }
    Node* head = &nodes[perm[0]];
    double t0=now_s(); double s=0;
    for(int r=0;r<40;r++){ for(Node* p=head;p;p=p->next) s+=p->v; }
    printf("pointer chase       : %7.1f ns/M  (s=%.0f)\n", (now_s()-t0)/40*n/1e6*1e6/1e6*1000, s); }
  // L1-hot short chain
  { const int m = 4096; double t0=now_s(); double s=0;
    for(int r=0;r<200000;m==4096?r++:r++) for(int i=0;i<m;i++) s+=vals[i];
    printf("L1-hot 4k loop      : %7.1f ns/M\n", (now_s()-t0)/200000*m/1e6*1e6/1e6*1000); }
  return 0;
}
