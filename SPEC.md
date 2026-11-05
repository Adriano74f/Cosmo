# Cosmo — spécification du langage

Cosmo est un petit langage impératif au thème spatial. Il est transpilé en Python.
Les fichiers source ont l'extension `.cosmo` et sont encodés en UTF-8.

```
# Calcul de trajectoire
mission double(n) {
    atterris n * 2;
}

module x = 5;
detecte x > 3 {
    transmets "grand", double(x);
} sinon {
    transmets "petit";
}
```

## 1. Vocabulaire du langage

| Cosmo | Rôle | Équivalent Python |
|---|---|---|
| `module x = 5;` | déclarer une variable | `x = 5` |
| `x = x + 1;` | réaffecter une variable déjà déclarée | `x = x + 1` |
| `mission f(a, b) { … }` | déclarer une fonction | `def f(a, b): …` |
| `atterris expr;` | renvoyer une valeur | `return expr` |
| `detecte … { } sinon detecte … { } sinon { }` | condition | `if / elif / else` |
| `orbite cond { … }` | boucle « tant que » | `while cond: …` |
| `survole i dans a..b { … }` | boucle sur un intervalle (b exclu) | `for i in range(a, b): …` |
| `transmets a, b;` | afficher | `print(a, b)` |
| `go` / `nogo` | booléens vrai / faux | `True` / `False` |
| `et`, `ou`, `non` | opérateurs logiques | `and`, `or`, `not` |

## 2. Lexique (étape du lexer)

### 2.1 Éléments ignorés

- Les espaces, tabulations et sauts de ligne séparent les tokens et sont ignorés.
- Un commentaire commence par `#` et s'arrête à la fin de la ligne.

### 2.2 Tokens

```ebnf
ENTIER   = chiffre , { chiffre } ;
IDENT    = lettre , { lettre | chiffre } ;        (* sauf les mots réservés *)
CHAINE   = '"' , { caractere | echappement } , '"' ;

chiffre    = "0" | "1" | … | "9" ;
lettre     = "a" | … | "z" | "A" | … | "Z" | "_" ;
caractere  = (* tout caractère sauf '"', '\' et le saut de ligne *) ;
echappement = "\" , ( '"' | "\" | "n" ) ;
```

- Les identifiants sont en ASCII et sensibles à la casse (`Vitesse` ≠ `vitesse`).
- Une chaîne ne peut pas s'étendre sur plusieurs lignes.
- Il n'y a pas de nombres à virgule : `0..10` est donc lu sans ambiguïté comme `0`, `..`, `10`.

**Mots réservés** : `module mission atterris detecte sinon orbite survole dans transmets go nogo et ou non`

**Symboles** : `+ - * / % == != < <= > >= = ( ) { } , ; ..`

Le lexer lit toujours le symbole **le plus long possible** : `<=` est un seul token, pas `<` suivi de `=`.

## 3. Grammaire (étapes du parser)

Notation EBNF : `{ x }` = x répété zéro fois ou plus, `[ x ]` = x optionnel, `|` = alternative,
`"..."` = token exact.

### 3.1 Programme et instructions

```ebnf
programme    = { declaration } , FIN ;
declaration  = mission | instruction ;

mission      = "mission" , IDENT , "(" , [ parametres ] , ")" , bloc ;
parametres   = IDENT , { "," , IDENT } ;
bloc         = "{" , { instruction } , "}" ;

instruction  = module | affectation | transmets | detecte
             | orbite | survole | atterris | appel_seul ;

module       = "module" , IDENT , "=" , expression , ";" ;
affectation  = IDENT , "=" , expression , ";" ;
transmets    = "transmets" , [ expression , { "," , expression } ] , ";" ;
detecte      = "detecte" , expression , bloc , [ "sinon" , ( detecte | bloc ) ] ;
orbite       = "orbite" , expression , bloc ;
survole      = "survole" , IDENT , "dans" , expression , ".." , expression , bloc ;
atterris     = "atterris" , [ expression ] , ";" ;
appel_seul   = appel , ";" ;
```

Remarques :

- Les missions ne se déclarent qu'au niveau principal, pas à l'intérieur d'un bloc.
- `affectation` et `appel_seul` commencent tous les deux par `IDENT`. Le parser les distingue
  grâce au token **suivant** (`=` ou `(`) : c'est le « regard en avant » de l'étape 3.
- `sinon detecte` permet d'enchaîner les conditions sans imbriquer les accolades.
- Une expression seule qui n'est pas un appel (`1 + 2;`) est refusée : elle ne servirait à rien.

### 3.2 Expressions

Chaque niveau utilise le niveau suivant, plus prioritaire.

```ebnf
expression   = disjonction ;
disjonction  = conjonction , { "ou" , conjonction } ;
conjonction  = negation , { "et" , negation } ;
negation     = "non" , negation | comparaison ;
comparaison  = somme , [ op_comp , somme ] ;
op_comp      = "==" | "!=" | "<" | "<=" | ">" | ">=" ;
somme        = produit , { ( "+" | "-" ) , produit } ;
produit      = unaire , { ( "*" | "/" | "%" ) , unaire } ;
unaire       = "-" , unaire | primaire ;
primaire     = ENTIER | CHAINE | "go" | "nogo" | appel | IDENT | "(" , expression , ")" ;
appel        = IDENT , "(" , [ arguments ] , ")" ;
arguments    = expression , { "," , expression } ;
```

### 3.3 Priorités et associativité

Du moins prioritaire au plus prioritaire (ce tableau servira de table de priorités au parser de Pratt, étape 5) :

| Niveau | Opérateurs | Associativité |
|---|---|---|
| 1 | `ou` | gauche |
| 2 | `et` | gauche |
| 3 | `non` (unaire) | — |
| 4 | `== != < <= > >=` | non associatif : `a < b < c` est une erreur |
| 5 | `+ -` | gauche |
| 6 | `* / %` | gauche |
| 7 | `-` (unaire) | — |
| 8 | appel `f(…)`, parenthèses | — |

Exemples : `1 + 2 * 3` vaut `1 + (2 * 3)` ; `non a et b` vaut `(non a) et b` ;
`10 - 3 - 2` vaut `(10 - 3) - 2`.

## 4. Sémantique

### 4.1 Valeurs

Cosmo n'a pas de types déclarés. Une valeur est :

- un **entier** (`42`, `-7`) ;
- une **chaîne** (`"Ada"`) ;
- un **booléen** : `go` (vrai) ou `nogo` (faux) ;
- **rien** : la valeur renvoyée par une mission qui ne renvoie rien.

### 4.2 Opérateurs

- `+ - *` : arithmétique entière. `+` concatène aussi deux chaînes.
- `/` : **division entière**, arrondie vers le bas comme le `//` de Python (`7 / 2` vaut `3`, `-7 / 2` vaut `-4`).
- `%` : reste de la division entière.
- Comparaisons : renvoient `go` ou `nogo`.
- `et` / `ou` : évaluation en court-circuit, comme en Python.
- Mélanger des types incompatibles (`"a" + 1`) ou diviser par zéro provoque une **erreur à l'exécution**.

### 4.3 Vérité

Une condition (`detecte`, `orbite`) peut être n'importe quelle expression.
Sont considérés comme faux : `nogo`, `0`, `""` et rien. Tout le reste est vrai.

### 4.4 Variables et portées

- Une variable doit être **déclarée avec `module`** avant d'être lue ou réaffectée.
- Chaque bloc `{ … }` ouvre une **nouvelle portée** : une variable déclarée dans un bloc
  n'existe plus après l'accolade fermante.
- **Pas de masquage** : déclarer une variable qui porte le nom d'une variable encore visible
  (même portée ou portée englobante) est une erreur.
- Une variable ne peut pas porter le nom d'une mission (sinon `f(1)` serait ambigu).

Pourquoi interdire le masquage ? En Python, un `if` ou un `while` n'ouvre pas de nouvelle portée.
Si Cosmo autorisait le masquage, `module x` dans un bloc écraserait le `x` extérieur une fois
traduit en Python. L'interdire garde la traduction simple et le comportement prévisible.

### 4.5 Missions (fonctions)

- Une mission peut être appelée **avant** sa déclaration dans le fichier : cela permet la récursivité croisée.
- Deux missions ne peuvent pas porter le même nom, et deux paramètres d'une même mission non plus.
- Un appel doit fournir **exactement** le nombre d'arguments attendu (vérifié à la compilation).
- Une mission est **isolée** : elle ne voit que ses paramètres, ses propres variables et les autres missions.
  Elle n'a pas accès aux variables déclarées au niveau principal.
- `atterris` termine la mission. `atterris;` sans valeur, ou la fin du bloc, renvoie **rien**.
- `atterris` en dehors d'une mission est une erreur.

### 4.6 Boucles

- `orbite cond { … }` répète le bloc tant que `cond` est vraie.
- `survole i dans a..b { … }` donne à `i` les valeurs `a`, `a+1`, …, `b-1`.
  `a` et `b` sont évalués une seule fois, avant la boucle. `i` est déclarée automatiquement
  dans la portée de la boucle et suit la règle de non-masquage.

### 4.7 Affichage

`transmets a, b, c;` affiche les valeurs séparées par une espace, puis un saut de ligne.
Les chaînes s'affichent sans guillemets, les booléens comme `go` / `nogo` et l'absence de valeur comme `rien`.
`transmets;` affiche une ligne vide.

## 5. Erreurs

Toute erreur indique sa **ligne** et sa **colonne** (en commençant à 1), au format :

```
[ligne:colonne] erreur <phase> : <message>
```

| Phase | Exemples |
|---|---|
| lexicale | caractère inconnu (`@`), chaîne non terminée |
| syntaxique | `;` attendu, `}` manquant, expression attendue, `a < b < c` |
| sémantique | variable non déclarée, déclaration en double, masquage, mauvais nombre d'arguments, mission inconnue, `atterris` hors mission |
| de génération | programme valide mais trop imbriqué pour Python |
| exécution | division par zéro, types incompatibles (remontées par Python) |

Le parser tente de **continuer après une erreur** (étape 6) pour en signaler plusieurs en une seule compilation :
il reprend à l'instruction suivante. Seules une erreur lexicale et une imbrication trop profonde arrêtent l'analyse.

## 6. Traduction vers Python (étape 8)

- Les identifiants Cosmo sont préfixés (par exemple `x` devient `c_x`) : un programme Cosmo peut ainsi
  nommer une variable `class` ou `print` sans entrer en conflit avec Python.
- `/` devient `//`, `go` / `nogo` deviennent `True` / `False`, `rien` devient `None`.
- `transmets` appelle une petite fonction d'affichage générée en tête du fichier, qui écrit
  `go`, `nogo` et `rien` au lieu de `True`, `False` et `None`.
- Les missions sont générées avant le niveau principal : elles existent ainsi dès la première instruction.
- Les limites de Python s'appliquent au code généré : au-delà de 20 boucles imbriquées, ou de 100 niveaux
  d'indentation, la compilation échoue avec une `erreur de génération`.

## 7. Programmes d'exemple

Chaque programme `exemples/NN_nom.cosmo` a sa sortie attendue dans `NN_nom.attendu`.
Chaque programme `erreurs/NN_nom.cosmo` a le message d'erreur attendu dans `NN_nom.attendu`.

| Fichier | Ce qu'il montre |
|---|---|
| `01_premier_contact` | variables, chaînes, priorités, division entière, booléens |
| `02_fibonacci` | mission récursive, `survole` |
| `03_compte_a_rebours` | `orbite`, `detecte / sinon detecte / sinon`, réaffectation |
| `04_controle_mission` | chaînes, `et` / `ou` / `non`, mission sans valeur (`rien`) |
| `05_portees` | variables locales, portée d'un bloc |
| `erreurs/01` à `05` | une erreur de chaque phase de compilation |

## 8. Hors périmètre (évolutions possibles)

Nombres à virgule, listes, types déclarés (extension 12), `casse` / `continue` dans les boucles,
missions imbriquées.
