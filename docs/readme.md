
L'admin du tenant saisie l'adresse mail de la personne à inviter et obtient un code valable 1h pour join le tenant (le send par mail ?)
Auth -> l'utilsiateur crée son compte on lui propose de créer un tenant ou de saisir un code unique pour rejoindre un tenant (reçu par mail ?)
L'admin valide  l'inscription


# Tenants

GET    /tenant      - Lister les tenants
GET    /tenant/{id} - Récupérer un tenant
POST   /tenant      - Créer un tenant
PUT    /tenant/{id} - modifier un tenant
DELETE /tenant/{id} - supprimer un tenant

# Auth

GET /oauth2/callback
GET /oauth2/renew
GET /oauth2/logout
GET /oauth2/auth

# Users

GET     /user      - lister  les users
GET     /user/{id} - voir un utilisateur

# Users tenant

GET     /tenant/{id}/user - lister les users d'un tenant
GET     /tenant/{id}/user/{id} - récupérer un user d'un tenant
PUT     /tenant/{id}/user/{id} - modifier l'utilisateur d'un tenant
DELETE  /tenant/{id}/user/{id} - Révoque l'accès de l'utilisateur au tenant

# Users tenant join
POST    /tenant/{id}/code        - Crée un code de jointure (contient l'adresse mail et renvoie un code + par mail à  la personne indiqué)
PUT     /tenant/{id}/code/{code} - Joint  l'utilsiateur conecté au tenant (doit être confirmé par un admin)
PATCH   /tenant/{id}/user/{id}   - Valide la jointure  de l'utilsiateur au tenant

# Patient

GET     /tenant/{tid}/patient      - Lister les patients
POST    /tenant/{tid}/patient      - ajouter un patient
GET     /tenant/{tid}/patient/{id} - information d'un patient
PUT     /tenant/{tid}/patient/{id} - mettre à jour les information d'un patient
DELETE  /tenant/{tid}/patient/{id} - Supprimer un patient

# prescriptions

GET        /tenant/{tid}/patient/{paid}/prescription                   - Lister les prescriptions d'un patient
POST       /tenant/{tid}/patient/{paid}/prescription    	       - Ajouter une prescription au patient
GET        /tenant/{tid}/prescription/{peid}            	       - donne les informations d'une prescription
PUT        /tenant/{tid}/prescription/{peid}            	       - modiifier les informations d'un prescription
POST       /tenant/{tid}/prescription/{peid}/upload     	       - upload de l'ordonance relative à une prescription
POST       /tenant/{tid}/prescription/{peid}/line       	       - Ajouter une ligne à la prescription
PUT        /tenant/{tid}/prescription/{peid}/line/{line_id}            - modifier une ligne de prescription
DELETE     /tenant/{tid}/prescription/{peid}/line/{line_id}            - supprimer une ligne de prescription
POST       /tenant/{tid}/prescription/{peid}/whell/{w_id}/generate     - génère  la liste des médicament  par case

# Box

GET      /tenant/{tid}/box          		     - Lister les boxs
DELETE   /tenant/{tid}/box          		     - Supprimer une box du tenant
POST     /tenant/{tid}/box                           - joindre une box au tenant
GET      /tenant/{tid}/box/{bid}/events               - Liste les évènement d'une box

# Affectation box patient

PATCH    /tenant/{tid}/box/{bid}/patient/{pid}       - Affecter une box à un patient
PATCH    /tenant/{tid}/box/{bid}   		     - désaffecter une box à un patient


# Wheel

GET      /tenant/{tid}/wheel          		     - Lister les roues de distribution
DELETE   /tenant/{tid}/wheel          		     - Supprimer les roues de distribution du tenant
POST     /tenant/{tid}/wheel                         - joindre les roues de distribution au tenant
GET      /tenant/{tid}/wheel/{wid}/events            - Liste les évènement d'une roue
GET      /tenant/{tid}/wheel/{wid}		     - Récupère les informations d'une roue  et l'état de ses cases
PATCH    /tenant/{tid}/wheel/{wid}		     - Change l'état d'une Wheel (en préparation/ stock/ retour patient …)

# Affectation roue - box

PATCH    /tenant/{tid}/wheel/{wid}/box/{bid}         - Affecter une roue de distribution à une wheel
PATCH    /tenant/{tid}/box/{wid}   		     - désaffecter  une roue de distribution à une whell

# Wheel slot

PUT      /tenant/{tid}/wheel/{wid}/slots/{sid}       - Modifie le contenue d'une case
PATCH	 /tenant/{tid}/wheel/{wid}/slots/{sid}       - valide  le contenue d'une case

