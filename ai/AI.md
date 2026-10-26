# AI.md

Cu Claude în chat am analizat materialele și capcanele, am scris notițele (probabil cea mai importantă parte dpmdv.), CLAUDE.md și promptul pentru Claude Code și am revizuit DESIGN.md. 

Claude Code, cu skill-urile superpowers, a scris codul și testele, iar eu aprobam planul, textul și config-ul la punctele de oprire. 

## O sugestie pe care am refuzat-o

Planul lui Claude Code complica prea mult partea de analiză din secțiunea E, făcuse un cod pe mai multe fișiere, cu mult mai multe linii de cod față de ce mi-aș fi dorit.

L-am oprit și am aprobat, cu amendamente, o simplificare pe altă ramură: patru tipuri fixe de relații, variantele de propoziții într-un tabel din config, 5 module.

Am oprit codul deoarece era mult prea mare având în vedere că output-ul e doar pe secțiunea E.


## Unde a greșit AI-ul și cum am prins

CLAUDE.md, scris cu ajutorul AI, avea regula: dacă o denumire alternativă din config prinde două rânduri în registru, verificarea config-ului pică și nu se mai scrie niciun draft.

Am prins-o la primul punct de oprire din Claude Code, când am revizuit planul împreună cu Claude din chat. 

Regula trata ca eroare de config o problemă care vine din registru. 

Programul va fi rulat pe un alt registru 2025, iar un registru cu ambele etichete pentru diversificare, cea veche și cea nouă, ar fi oprit tot raportul.


## O decizie păstrată pentru mine

Programul nu generează text. 

Toate textele, de la A.1 la E.2, vor veni din șabloane aprobate de oameni (în livrare există doar cel pentru E), pentru că formulările se pot schimba prin legislație, prin regulile UE despre algoritmi sau prin schimbări în companie. 

Programul completează doar cifrele și anii, alege direcția dintr-o listă închisă ("în creștere", "în scădere"), cu mărimea schimbării ("în scădere cu 2,1 % față de 151,9 mil. lei"), și alege între variante de propoziții scrise de oameni.

Singurul text pe care îl scrie singur e golul [de completat: motiv], cu motivul luat din config.

## Ce n-aș lăsa niciodată AI-ul să facă singur

Să pună în raport cifre, direcții, cauze sau formulări, să aleagă între surse care nu se potrivesc, să confirme un fapt ori să aprobe un șablon sau o decizie. 

De aceea programul nu folosește niciun LLM: fiecare cuvânt din raport vine dintr-un șablon aprobat de un om, din lista închisă de direcții sau dintr-o cifră ori un fapt cu sursă.