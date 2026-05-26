# Configuration de la persistance des données sur Render

## Modifications apportées

Votre application a été modifiée pour utiliser PostgreSQL au lieu de fichiers JSON locaux. Cela garantit que les données restent sauvegardées même lorsque l'application se met en veille ou redémarre.

## Configuration sur Render

### 1. Créer une base de données PostgreSQL

1. Connectez-vous à votre compte Render (https://render.com)
2. Cliquez sur **"New +"** puis **"PostgreSQL"**
3. Configurez votre base de données :
   - **Name** : Donnez un nom (ex: `bcnhub-bingo-db`)
   - **Database** : Laissez le nom par défaut ou choisissez-en un
   - **User** : Laissez le nom par défaut
   - **Region** : Choisissez la même région que votre application web
   - **Plan** : Sélectionnez **"Free"** (gratuit)
4. Cliquez sur **"Create Database"**

### 2. Connecter la base de données à votre application

1. Une fois la base créée, allez sur la page de votre **Web Service**
2. Dans l'onglet **"Environment"**, ajoutez une nouvelle variable d'environnement :
   - **Key** : `DATABASE_URL`
   - **Value** : Copiez l'URL de connexion depuis votre base PostgreSQL
     - Allez sur votre base de données PostgreSQL
     - Copiez la valeur de **"Internal Database URL"** (recommandé) ou **"External Database URL"**
3. Sauvegardez les changements

### 3. Redéployer l'application

1. Poussez les modifications sur votre repository Git :
   ```bash
   git add .
   git commit -m "Add PostgreSQL support for data persistence"
   git push
   ```

2. Render va automatiquement redéployer votre application avec les nouvelles dépendances

### 4. Initialisation automatique

Au premier démarrage, l'application va :
- Créer automatiquement les tables nécessaires (`users` et `items`)
- Charger les données initiales depuis `items.json` si la table est vide
- Les données seront désormais persistantes !

## Fonctionnement en développement local

L'application fonctionne toujours en mode local sans PostgreSQL :
- Si la variable `DATABASE_URL` n'est pas définie, elle utilisera les fichiers JSON locaux
- Cela vous permet de développer sans avoir besoin d'une base de données locale

## Structure de la base de données

### Table `items`
- `id` : Identifiant unique (auto-incrémenté)
- `item_text` : Texte de l'élément (unique)
- `votes` : Nombre de votes

### Table `users`
- `username` : Nom d'utilisateur (clé primaire)
- `is_connected` : Statut de connexion
- `has_bingo` : A réalisé un bingo
- `grid` : Grille de bingo (format JSON)
- `manifest_choices` : Choix du manifest (format JSON)
- `manifest_submitted` : A soumis le manifest

## Vérification

Pour vérifier que tout fonctionne :
1. Consultez les logs de votre application sur Render
2. Vous devriez voir le message de connexion à la base de données
3. Testez votre application : les données devraient persister entre les redémarrages

## Sauvegarde

Render effectue des sauvegardes automatiques de votre base de données PostgreSQL. Vous pouvez également créer des sauvegardes manuelles depuis le dashboard Render.
