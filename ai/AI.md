# AI.md

Cu Claude în chat am analizat materialele și capcanele, am scris notițele, CLAUDE.md și promptul pentru Claude Code și am revizuit DESIGN.md. Claude Code, cu skill-urile superpowers, a scris codul și testele, iar eu aprobam planul, textul și config-ul la puncte de oprire. Conversațiile sunt în ai/conversations/, needitate.

## O sugestie pe care am refuzat-o

Planul lui Claude Code ducea la un program prea complicat pentru o felie din secțiunea E: un mini-limbaj de șabloane cu [dacă] / [altfel], un evaluator de expresii pentru relații, o protecție separată pentru unități (×1.000) și 7 module. Le aprobasem chiar eu la primul punct de oprire. După patru task-uri, codul avea 531 de linii și acoperea mai puțin de jumătate din program. L-am oprit în task-ul 5 și am aprobat, cu amendamente, un plan de simplificare pe o ramură separată: patru tipuri fixe de relații, variantele de propoziții într-un tabel din config, 5 module. Versiunea veche a rămas în ramura t5-evaluator.

Motivul: cel mai mare risc e rularea de anul viitor fără autori, iar eu trebuie să explic fiecare linie. Am refuzat apoi tăieturile care m-ar fi adus la 500 de linii, pentru că scoteau verificări sau făceau mesajele de eroare mai vagi. Codul final are circa 760 de linii.

## Unde a greșit AI-ul și cum am prins

CLAUDE.md, scris cu Claude în chat, cerea ca o denumire din config care se potrivește pe două rânduri din registru să oprească tot draftul. Claude Code a notat în plan costul (un registru cu eticheta veche și cu cea nouă pentru diversificare oprește rularea), dar a recomandat regula "așa cum cere specificația". Am prins-o când am trecut prin plan decizie cu decizie, împreună cu Claude în chat: programul rulează neschimbat pe alt registru, iar o problemă din registru nu e o eroare de config. Acum cifra afectată devine gol și draftul merge mai departe. Tot atunci am adus la zero toleranța de 0,05 mil. lei pe sume.

A doua greșeală a prins-o revizuirea de cod independentă pe care o cerusem în prompt pentru final. Revizorul a găsit că o cifră verificată față de o cifră aflată în conflict trecea drept "ok", iar tabelul de mutații nu vedea asta. Pe tabelul extins cu cazurile lui, fără corectură apar 14 cifre greșite în text; cu corectura, zero.

## O decizie păstrată pentru mine

Rata de solvabilitate: registrul spune 187,4 %, ca în 2024, iar calculul dă 197,4 %. Nu am lăsat niciun AI să aleagă și nu am ales nici eu: alegerea ține de CFO și de actuariat, iar o decizie din config cere doi oameni diferiți. Până atunci, rata rămâne gol.

Tot pentru mine am păstrat confirmarea faptelor și aprobarea textului, iar Claude Code avea interdicție să le scrie. Când modificările mele în config nu se salvaseră, a refuzat să le completeze în locul meu. Le-am dictat apoi, iar commit-ul spune că le-am decis eu după diff. Textul l-am aprobat doar dacă diff-ul față de aprobarea anterioară conținea numai linia nouă; așa a ieșit la iveală un spațiu șters din greșeală de Claude Code.

## Ce n-aș lăsa niciodată AI-ul să facă singur

Să pună în raport cifre, direcții, cauze sau formulări, să aleagă între două surse care nu se potrivesc, să confirme un fapt sau să aprobe un șablon ori o decizie. De aceea programul nu folosește niciun LLM: orice cuvânt din raport vine dintr-un șablon aprobat de un om sau dintr-o cifră ori un fapt cu sursă.
