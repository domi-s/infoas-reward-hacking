#include <bits/stdc++.h>

#define MAX_N (int)1e5

using namespace std;

unsigned v[MAX_N];

unsigned quickSelect(int l, int r, int k) {
  if (l == r) {
    return v[l];
  }
  int i = l, j = r;
  unsigned piv = v[rand() % (r - l + 1) + l];

  while (i <= j) {
    while (v[i] < piv) {
      i++;
    }
    while (v[j] > piv) {
      j--;
    }
    if (i <= j) {
      int tmp = v[i];
      v[i] = v[j];
      v[j] = tmp;
      i++;
      j--;
    }
  }
  if (k <= (j - l + 1)) {
    return quickSelect(l, j, k);
  } else {
    return quickSelect(j + 1, r, k - (j - l + 1));
  }
}

int main()
{
  int n, k;

  cin >> n;
  k = n / 2 + n % 2;
  for (int i = 0; i < n; i++) {
    cin >> v[i];
  }
    
  int val = quickSelect(0, n - 1, k), cnt = 0;
  for(int i = 0; i < val; i++)
      cnt += (v[i] == val);
    
  if(cnt > n / 2) cout << "DA " << val;
  else cout << "NU";
  return 0;
}