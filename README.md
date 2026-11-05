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
source .cosmo → lexer → parser → analyse sémantique → backend → exécution
                (tokens)  (arbre)   (portées, erreurs)   (Python, ou Cosmo formaté)
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

Depuis le dossier du projet (détails dans [SPEC.md](SPEC.md), section 7) :

```bash
python -m cosmo run exemples/02_fibonacci.cosmo        # exécuter un programme
python -m cosmo transpile exemples/02_fibonacci.cosmo  # voir le Python généré
python -m cosmo formate exemples/02_fibonacci.cosmo    # afficher le programme bien présenté
python -m cosmo verifie exemples/02_fibonacci.cosmo    # chercher les erreurs, sans exécuter
python -m cosmo tokens exemples/02_fibonacci.cosmo     # voir les tokens
python -m cosmo arbre exemples/02_fibonacci.cosmo      # voir l'arbre
python -m cosmo                                        # session interactive (REPL)
```

Lancer les vérifications :

```bash
uv run pytest          # les tests
uv run mypy            # le typage, en mode strict (réglages dans pyproject.toml)
uv run ruff check      # le style
```

## Avancement

- [x] Étape 1 : spécification du langage
- [x] Étape 2 : types de token et classe `Token`
- [x] Étape 3 : lexer
- [x] Étape 4 : nœuds de l'arbre syntaxique
- [x] Étape 5 : parser des expressions (Pratt)
- [x] Étape 6 : parser des instructions et récupération d'erreurs
- [x] Étape 7 : analyse sémantique
- [x] Étape 8 : génération de Python et exécution des exemples
- [x] Étape 9 : ligne de commande et REPL
- [x] Étape 10 : `mypy --strict`, backend en `Protocol`, formateur
