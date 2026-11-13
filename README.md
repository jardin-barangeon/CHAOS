# RPTPFR CHAOS — V3

Jeu de cartes multijoueur temps réel, 2 à 8 joueurs, solo avec robots, salons publics et privés.

## Installation locale

```bash
pip install -r requirements.txt
python server.py
```

Ouvrir http://localhost:8000 (pour les amis distants, déployer sur Render).

## Déploiement Render

Créer un service Web Python pointant sur ce dossier (ou dépôt GitHub), commande de build `pip install -r requirements.txt`, commande de démarrage `python server.py`. Render définit automatiquement `PORT`. Une seule instance est nécessaire : salons en mémoire, perdus au redémarrage.

## Cartes spéciales

- Piège routier : cible le prochain joueur, qui pioche 2 cartes au début de son tour.
- Échange : échange toute la main du joueur avec celle d'un adversaire choisi.
- Convoi fou : fait tourner les mains de tous les joueurs d'un siège.
- Les cartes classiques (+2, +4, inversion, skip, joker) restent présentes.

## Marque RPTPFR

Les cartes affichent la marque RPTPFR en typographie intégrée. Le fichier du logo officiel n'était pas disponible dans les fichiers du projet : pour l'intégrer à l'identique, fournir le PNG transparent original. Aucun logo approximatif n'a été substitué.

## Site RPTPFR

Le jeu est une application Python indépendante. Le plus simple est de l'héberger sur un sous-domaine ou une URL Render séparée, puis d'ajouter un lien « Jouer à RPTPFR CHAOS » au site RPTPFR. Ne pas écraser le serveur existant des classements Trucky.


## V4 : logo et bulles d'aide
Le logo officiel `static/logo-rptpfr.png` figure sur les cartes et la pioche. Survole une carte spéciale avec la souris (ou sélectionne-la au clavier) pour lire son effet. Sur téléphone, un appui long peut afficher le titre natif de la carte selon le navigateur.


V5 : cartes redessinées, texte retiré des faces, icônes grandes, mini-logo, descriptions au survol/focus. Le moteur de jeu reste celui de V4.


## V6 : table de 4 joueurs
- 4 participants maximum, humains et robots confondus, dans tous les salons.
- Mode solo : sélectionner 1, 2 ou 3 robots (3 par défaut).
- L’hôte peut ajouter des robots dans un salon en attente, jusqu’à 4 places occupées.
- Les salons publics pleins ne sont plus listés.
- Le style des cartes V5 et le logo RPTPFR sont conservés.


## V7 — Table arcade
- Table elliptique, adversaires autour, mains adverses face cachée avec le logo officiel.
- Animations de distribution et de carte centrale, halo sur le joueur actif.
- Maximum 4 joueurs, bots compris (règle côté serveur).
- Installation : `pip install -r requirements.txt` puis `python server.py`.
- Pour inviter des amis hors réseau local, héberger le serveur sur une URL publique HTTPS/WebSocket.


## Version 8
- Accueil repensé (hero RPTPFR, cartes de modes, liste publique).
- Cartes et carte centrale conservées entre les messages d'état identiques : plus de flash à chaque tour.
- Animation de déplacement d'une carte jouée vers le centre lors de la confirmation du serveur.
- Avatars adverses mis à jour seulement quand leur main change.
- Aucun changement des règles ou du protocole réseau.

## V9 — Échange interactif
Joue une carte ÉCHANGE, puis clique directement sur les cartes ou l'avatar de l'adversaire à cibler. Échap annule la sélection. La cible est obligatoire et validée par le serveur.


## V10 — Ambiance sonore
- Musique originale de style lounge/casino, générée localement avec Web Audio (aucun fichier musical externe).
- Bruitages de carte jouée, pioche, piège, échange, tour et victoire.
- Boutons musique ON/OFF, effets ON/OFF et volume dans le coin inférieur droit.
- La musique démarre uniquement après un clic sur Musique ON (politique des navigateurs).
- Les sons ne sont pas transmis par WebSocket : chaque joueur contrôle son propre audio.


## V12
- Correction du déclenchement de la célébration : le serveur marque la partie terminée (`started=false`) dès la victoire. La V11 attendait à tort `started=true`, empêchant l'animation.
- La célébration est déclenchée sur chaque navigateur recevant le résultat du serveur, y compris ceux des perdants.
- Trois ambiances musicales instrumentales originales se succèdent automatiquement, sans répétition immédiate d'une seule boucle.
- Les sons restent soumis à l'autorisation audio du navigateur : un premier clic sur le jeu peut être nécessaire.


## V13 — Classement libre
- Score conservé entre les manches tant que le salon existe et que le joueur reste connecté.
- Le vainqueur gagne la somme des cartes restantes des autres joueurs : chiffres valeur faciale, passer/inversion/+2 20, piège 30, échange/convoi 40, joker/+4 50.
- Classement visible pendant la partie, récapitulatif et podium lors de la victoire.
- Le bouton Rejouer lance une nouvelle manche sans effacer les scores.
- Attention : les scores sont en mémoire, non persistés après déconnexion ou redémarrage du serveur.


## V14 — animations des cartes spéciales
Les cartes Piège routier, Échange, Convoi fou, Route barrée, Demi-tour, +2 et +4 déclenchent une animation et un bruitage distincts sur tous les navigateurs connectés. Les événements sont émis par le serveur, y compris quand un robot joue. Les bruitages suivent le bouton Effets ON/OFF et le volume général. L'animation est superposée à la table, sans recréer les cartes.
