# Cosmo

Cosmo est un petit langage de programmation impératif au thème spatial.
Son compilateur, écrit entièrement à la main, le traduit en Python.

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

## Documentation

- **Spécification complète du langage** : [SPEC.md](SPEC.md) (lexique, grammaire EBNF, sémantique, erreurs)
- **Programmes d'exemple** : `exemples/`, chacun accompagné de sa sortie attendue (`.attendu`)
- **Programmes erronés** : `erreurs/`, chacun accompagné du message d'erreur attendu (`.attendu`)

## Chaîne de compilation

```
source .cosmo → lexer → parser → analyse sémantique → génération de Python → exécution
                (tokens)  (arbre)   (portées, erreurs)   (code Python)
```

## Organisation du projet

```
projet/
├── README.md
├── SPEC.md        spécification du langage
├── exemples/      programmes valides et sorties attendues
├── erreurs/       programmes invalides et erreurs attendues
├── cosmo/         paquet Python : le compilateur
└── tests/         tests pytest
```

## Utilisation

Exécuter un programme (disponible à partir de l'étape 9) :

```bash
python -m cosmo run exemples/02_fibonacci.cosmo
```

Lancer les vérifications :

```bash
uv run pytest projet              # les tests
uv run mypy projet/cosmo          # le typage
uv run ruff check projet          # le style
```

## Avancement

- [x] Étape 1 : spécification du langage
- [x] Étape 2 : types de token et classe `Token`
- [x] Étape 3 : lexer
- [x] Étape 4 : nœuds de l'arbre syntaxique
- [x] Étape 5 : parser des expressions (Pratt)
- [x] Étape 6 : parser des instructions et récupération d'erreurs
- [ ] Étape 7 : analyse sémantique
- [ ] Étape 8 : génération de Python et exécution des exemples
- [ ] Étape 9 : ligne de commande et REPL
- [ ] Étape 10 : `mypy --strict`, backend en `Protocol`, formateur
