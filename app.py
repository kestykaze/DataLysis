from flask import Flask, render_template, request, redirect, url_for
import pymysql
import pandas as pd
import json
from database import get_connection
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
from scipy import stats as scipy_stats
import base64
from io import BytesIO

app = Flask(__name__)


# ───────────────────────────────────────────────
# PAGE D'ACCUEIL
# ───────────────────────────────────────────────
@app.route('/')
def index():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projets")
    projets = cursor.fetchall()
    conn.close()
    return render_template('index.html', projets=projets)   


# ───────────────────────────────────────────────
# CRÉER UN PROJET
# ───────────────────────────────────────────────
@app.route('/creer', methods=['GET', 'POST'])
def creer():
    if request.method == 'POST':
        nom         = request.form.get('nom', '').strip()
        description = request.form.get('description', '').strip()
        variables   = request.form.getlist('variables')

        if not nom:
            return render_template('creer.html', erreur="Le nom du projet est obligatoire.")

        conn   = get_connection()
        cursor = conn.cursor()                               # ✅ pas de dictionary=True
        cursor.execute("INSERT INTO projets (nom, description) VALUES (%s, %s)", (nom, description))
        projet_id = cursor.lastrowid

        for variable in variables:
            if variable.strip():
                cursor.execute(
                    "INSERT INTO variables (projet_id, nom) VALUES (%s, %s)",
                    (projet_id, variable.strip())
                )

        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    return render_template('creer.html')


#pour supprimer un projet si l'on veut
@app.route('/supprimer/<int:id>', methods=['POST'])
def supprimer(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM enregistrements WHERE projet_id = %s", (id,))
    cursor.execute("DELETE FROM variables WHERE projet_id = %s", (id,))
    cursor.execute("DELETE FROM projets WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))


# ───────────────────────────────────────────────
# SAISIR DES DONNÉES
# ───────────────────────────────────────────────
@app.route('/saisir/<int:id>', methods=['GET', 'POST'])
def saisir(id):
    conn   = get_connection()
    cursor = conn.cursor()                                   # ✅ DictCursor déjà dans get_connection()

    cursor.execute("SELECT * FROM projets WHERE id = %s", (id,))
    projet = cursor.fetchone()

    if projet is None:
        conn.close()
        return "Projet introuvable", 404

    cursor.execute("SELECT * FROM variables WHERE projet_id = %s", (id,))
    variables = cursor.fetchall()

    if request.method == 'POST':
        donnees = {}
        for variable in variables:
            valeur = request.form.get(variable['nom'], '')
            donnees[variable['nom']] = valeur

        cursor.execute(
            "INSERT INTO enregistrements (projet_id, donnees) VALUES (%s, %s)",
            (id, json.dumps(donnees))
        )
        conn.commit()
        conn.close()
        return redirect(url_for('saisir', id=id))

    conn.close()
    return render_template('saisir.html', projet=projet, variables=variables)


# ───────────────────────────────────────────────
# FONCTIONS UTILITAIRES
# ───────────────────────────────────────────────
def detecter_type(serie):
    try:
        numerique = pd.to_numeric(serie)
        if all(numerique == numerique.astype(int)):
            return 'discrete'                                
        else:
            return 'continue'                                
    except:
        return 'nominale'                                    

def convertir_image(fig):
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    image = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return image


def ana_quant(serie):
    serie = pd.to_numeric(serie)
    q1    = round(serie.quantile(0.25), 2)
    q3    = round(serie.quantile(0.75), 2)
    iqr   = round(q3 - q1, 2)
    borne_basse = q1 - 1.5 * iqr
    borne_haute = q3 + 1.5 * iqr
    outliers = serie[(serie < borne_basse) | (serie > borne_haute)].tolist()

    return {
        'moyenne'   : round(serie.mean(), 2),
        'mediane'   : round(serie.median(), 2),
        'mode'      : round(serie.mode()[0], 2),
        'ecart_type': round(serie.std(), 2),
        'variance'  : round(serie.var(), 2),
        'min'       : round(serie.min(), 2),
        'max'       : round(serie.max(), 2),
        'q1'        : q1,
        'q3'        : q3,
        'iqr'       : iqr,
        'outliers'  : outliers
    }


def ana_qual(serie):
    total        = len(serie)
    freq_absolue = serie.value_counts().to_dict()
    freq_relative = {
        k: round(v / total * 100, 2)
        for k, v in freq_absolue.items()
    }
    freq_cumulee = {}
    cumul = 0
    for k, v in freq_relative.items():
        cumul += v
        freq_cumulee[k] = round(cumul, 2)

    return {
        'mode'         : serie.mode()[0],
        'total'        : total,
        'freq_absolue' : freq_absolue,                      
        'freq_relative': freq_relative,
        'freq_cumulee' : freq_cumulee
    }


def generer_graphique_univ(serie, col, t):
    if t == 'continue':
        serie = pd.to_numeric(serie)
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.hist(serie.dropna(), bins=10, color='steelblue', edgecolor='white')
        ax.set_title(f'Distribution de {col}')
        ax.set_xlabel(col)
        ax.set_ylabel('Fréquence')
        plt.tight_layout()
        return convertir_image(fig)

    elif t == 'discrete':
        serie = pd.to_numeric(serie)
        fig, ax = plt.subplots(figsize=(6, 4))
        freq = serie.value_counts().sort_index()
        ax.bar(freq.index.astype(str), freq.values, color='steelblue', edgecolor='white')
        ax.set_title(f'Fréquences de {col}')
        ax.set_xlabel(col)
        ax.set_ylabel('Fréquence')
        plt.tight_layout()
        return convertir_image(fig)

    elif t == 'nominale':
        freq = serie.value_counts()
        if len(freq) > 7:
            top7   = freq.head(7)
            autres = freq.iloc[7:].sum()
            freq   = pd.concat([top7, pd.Series({'Autres': autres})])
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(freq.index, freq.values, color='steelblue', edgecolor='white')
        ax.set_title(f'Fréquences de {col}')
        ax.set_xlabel(col)
        ax.set_ylabel('Fréquence')
        ax.tick_params(axis='x', rotation=45)
        plt.tight_layout()
        return convertir_image(fig)


def analyser_bivariee(df, col1, col2, types_colonnes):
    t1 = types_colonnes[col1]
    t2 = types_colonnes[col2]

    # Quanti × Quanti
    if t1 in ['continue', 'discrete'] and t2 in ['continue', 'discrete']:
        s1 = pd.to_numeric(df[col1])
        s2 = pd.to_numeric(df[col2])

        corr  = round(s1.corr(s2), 2)
        force = "forte" if abs(corr) >= 0.7 else "modérée" if abs(corr) >= 0.3 else "faible"
        signe = "positive" if corr > 0 else "négative"

        pente, origine, r_value, p_value, _ = scipy_stats.linregress(s1, s2)
        r2      = round(r_value ** 2, 2)
        qualite = "bon" if r2 >= 0.7 else "moyen" if r2 >= 0.3 else "faible"
        significatif = "statistiquement significatif" if p_value < 0.05 else "non statistiquement significatif"

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.scatter(s1, s2, color='steelblue', edgecolor='white', label='Observations')
        x_line = [s1.min(), s1.max()]
        y_line = [pente * x + origine for x in x_line]
        ax.plot(x_line, y_line, color='red', label=f'y = {round(pente,2)}x + {round(origine,2)}')
        ax.set_xlabel(col1)
        ax.set_ylabel(col2)
        ax.set_title(f'{col1} vs {col2}')
        ax.legend()
        plt.tight_layout()
        graphique = convertir_image(fig)

        return {
            'type'       : 'quanti_quanti',
            'variable1'  : col1,
            'variable2'  : col2,
            'correlation': corr,
            'covariance' : round(s1.cov(s2), 2),
            'regression' : {
                'pente'   : round(pente, 4),
                'origine' : round(origine, 4),
                'r2'      : r2,
                'p_value' : round(p_value, 4),
                'equation': f"y = {round(pente,2)}×{col1} + {round(origine,2)}"
            },
            'graphique'     : graphique,
            'interpretation': (
                f"La corrélation entre '{col1}' et '{col2}' est {force} et {signe} ({corr}). "
                f"La régression donne : y = {round(pente,2)}×{col1} + {round(origine,2)}. "
                f"Le modèle est {qualite} (R² = {r2}) et est {significatif} (p = {round(p_value,4)})."
            )
        }

    # Quali × Quanti
    elif (t1 == 'nominale' and t2 in ['continue', 'discrete']) or \
         (t2 == 'nominale' and t1 in ['continue', 'discrete']):

        col_qual  = col1 if t1 == 'nominale' else col2
        col_quant = col2 if t1 == 'nominale' else col1

        serie_quant    = pd.to_numeric(df[col_quant])
        groupes        = df[col_qual].unique()
        donnees_groupes = [serie_quant[df[col_qual] == g].dropna() for g in groupes]

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.boxplot(donnees_groupes, labels=groupes)
        ax.set_title(f'{col_quant} selon {col_qual}')
        ax.set_xlabel(col_qual)
        ax.set_ylabel(col_quant)
        plt.tight_layout()
        graphique = convertir_image(fig)

        moyennes = df.groupby(col_qual)[col_quant].apply(
            lambda x: round(pd.to_numeric(x).mean(), 2)
        ).to_dict()

        return {
            'type'          : 'quali_quanti',
            'variable1'     : col_qual,
            'variable2'     : col_quant,
            'moyennes'      : moyennes,
            'graphique'     : graphique,
            'interpretation': (
                f"La moyenne de '{col_quant}' varie selon '{col_qual}' : "
                f"{', '.join([f'{k} → {v}' for k, v in moyennes.items()])}."
            )
        }

    # Quali × Quali
    elif t1 == 'nominale' and t2 == 'nominale':
        tableau = pd.crosstab(df[col1], df[col2])

        fig, ax = plt.subplots(figsize=(8, 5))
        tableau.plot(kind='bar', ax=ax, edgecolor='white')
        ax.set_title(f'{col1} vs {col2}')
        ax.set_xlabel(col1)
        ax.set_ylabel('Fréquence')
        plt.tight_layout()
        graphique = convertir_image(fig)

        return {
            'type'          : 'quali_quali',
            'variable1'     : col1,
            'variable2'     : col2,
            'tableau_croise': tableau.to_dict(),
            'graphique'     : graphique,
            'interpretation': (
                f"Le tableau croisé entre '{col1}' et '{col2}' "
                f"montre la distribution conjointe des deux variables qualitatives."
            )
        }

    # Cas impossible (deux variables identiques ou types non gérés)
    return {
        'type'   : 'erreur',
        'message': "Impossible d'analyser ces deux variables ensemble."
    }


# ───────────────────────────────────────────────
# ANALYSER
# ───────────────────────────────────────────────
@app.route('/analyser/<int:id>', methods=['GET', 'POST'])
def analyser(id):
    conn   = get_connection()
    cursor = conn.cursor()                                   

    cursor.execute("SELECT * FROM projets WHERE id = %s", (id,))
    projet = cursor.fetchone()

    cursor.execute("SELECT donnees FROM enregistrements WHERE projet_id = %s", (id,))
    enregistrements = cursor.fetchall()
    conn.close()

    donnees_liste = [json.loads(e['donnees']) for e in enregistrements]
    df = pd.DataFrame(donnees_liste)

    types_colonnes = {}
    for col in df.columns:
        types_colonnes[col] = detecter_type(df[col])

    colonnes = list(df.columns)

    stats_toutes = {}
    for col in colonnes:
        t = types_colonnes[col]
        if t in ['continue', 'discrete']:
            stats_toutes[col] = ana_quant(df[col])
        else:
            stats_toutes[col] = ana_qual(df[col])

    graphique_univ = None
    variable_univ  = None
    resultat_biv   = None

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'graphique_univ':
            variable_univ  = request.form['variable']
            t              = types_colonnes[variable_univ]
            graphique_univ = generer_graphique_univ(df[variable_univ], variable_univ, t)

        elif action == 'bivariee':
            col1         = request.form['variable1']
            col2         = request.form['variable2']
            resultat_biv = analyser_bivariee(df, col1, col2, types_colonnes)

    return render_template(
        'analyser.html',
        projet=projet,
        colonnes=colonnes,
        types_colonnes=types_colonnes,
        stats_toutes=stats_toutes,
        graphique_univ=graphique_univ,
        variable_univ=variable_univ,
        resultat_biv=resultat_biv
    )


if __name__ == '__main__':
    app.run(debug=True, port=5001)