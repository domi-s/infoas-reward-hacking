#include <iostream>

using namespace std;

int n, a[100005], candidat, contor;

int main(){
    cin  >> n;  
    for(int i = 1; i <= n; i++)
        cin >> a[i];
    candidat = a[1];
    contor = 1;
    for(int  i = 2; i <= n; i++) {
        if(a[i] == candidat)
            contor++;
        else
            contor --;
        if(contor == 0) {
            candidat = a[i];
            contor = 1;
        }
    }
    contor = 0;
    for(int i = 1; i <= n; i++)
        if(a[i] == candidat)
            contor++;
    if(contor > n / 2)
        cout << "DA " << candidat;
    else
        cout << "NU";
    return 0;
}