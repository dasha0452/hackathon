from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///case.db'
db = SQLAlchemy(app)


class Case(db.Model): #таблица бд для кейса хакатона
    id = db.Column(db.Integer, primary_key=True)
    case_name = db.Column(db.String(200))
    case_description = db.Column(db.Text)
    criteria = db.relationship('Criteria', backref='case', lazy=True)

    def repr(self):
        return '<Case%r>' % self.id


class Criteria(db.Model): #таблица бд для критериев кейса хакатона
    id = db.Column(db.Integer, primary_key=True)
    criteria_name = db.Column(db.String(100))
    points = db.Column(db.Integer)
    id_case = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False)

    def repr(self):
        return '<Criteria%r>' % self.id


class Evaluation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    player = db.relationship('Player', backref='evaluations')
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False)
    case = db.relationship('Case', backref='evaluations')
    jury_id = db.Column(db.Integer, db.ForeignKey('juries.id'), nullable=False)
    jury = db.relationship('Jury', backref='evaluations')
    points = db.Column(db.Integer)

    def __repr__(self):
        return f"<Evaluation object with id {self.id}>"

    # Метод для добавления баллов за критерий
    def add_criterion_score(self, criterion, score):
        if not hasattr(self, 'criterion_scores'):
            self.criterion_scores = []
        self.criterion_scores.append({'criterion': criterion, 'score': int(score)})

    # Метод для получения всех баллов за критерии
    def get_all_criterion_scores(self):
        return self.criterion_scores

    # Метод для получения общего количества баллов
    def get_total_score(self):
        return sum(score['score'] for score in self.criterion_scores)

    # Метод для обновления оценки, если она уже существует
    def update_evaluation(self, existing_criterion, score):
        if any(criterion['criterion'] == existing_criterion for criterion in self.get_all_criterion_scores):
            # Критерий уже существует, обновляем его счет
            for criterion in self.criterion_scores:
                if criterion['criterion'] == existing_criterion:
                    criterion['score'] = int(score)
        else:
            self.criterion_scores.append({'criterion': existing_criterion, 'score': int(score)})
        self.points = sum(score['score'] for score in self.criterion_scores)



@app.route('/')
def add_case():
    return render_template('add_case.html')


@app.route('/save_case', methods=['POST'])
def save_case():
    case_name = request.form['case_name']
    case_description = request.form['description']

    new_case = Case(case_name=case_name, case_description=case_description)
    db.session.add(new_case)
    game_id = session.get('game_id')
    game = Games.query.filter_by(id=game_id).first()
    game.hackathon_id = new_case.id
    criteria_names = request.form.getlist('criteria')
    points_list = request.form.getlist('points')

    for i in range(len(criteria_names)):
        new_criteria = Criteria(criteria_name=criteria_names[i], points=int(points_list[i]), case=new_case)
        db.session.add(new_criteria)

    db.session.commit()

    return redirect('/view_case/{}'.format(new_case.id))


@app.route('/view_case/<int:case_id>')
def view_case(case_id):
    case = Case.query.get(case_id)
    return render_template("index.html", case = case)


@app.route('/view_for_participants/<int:case_id>')
def view_for_participants(case_id):
    case = Case.query.get(case_id)
    criteria = Criteria.query.filter_by(case=case).all()
    return render_template("view_for_participants.html", case=case, criteria=criteria)


@app.route('/jury_participants')
def participants():
    a = {}
    code = session.get('codes_id')
    codes_id = PlayerCodesAssociation.query.filter_by(codes_id=code).all()
    i = 1
    for code_id in codes_id:
        player = Player.query.get(code_id.player_id)
        a[i] = player.name if player else None
        i+=1
    session['players'] = a
    return render_template("participants.html", slovar=a)


@app.route('/jury_№participant', methods=['GET', 'POST'])
def participantss():
    code_id = session.get('codes_id')
    code = Codes.query.get(code_id)
    game = Games.query.get(code.game_id)
    case = Case.query.get(game.hackathon_id)
    session['case_id'] = case.id
    player_number = request.args.get('player_number')
    igrok = session.get('players').get(int(player_number))
    session['igrok'] = player_number
    return render_template("dlya№.html", case=case, igrok=igrok,player_number=player_number)


@app.route('/save_data', methods=['GET', 'POST'])
def process_form():
    if request.method == 'POST':
        # Получаем все значения input элементов с именем 'participant_score'
        igrok = session.get('igrok')
        participant_scores = request.form.getlist('participant_score')
        player = Player.query.filter_by(id=igrok).first()
        case_id = session.get('case_id')
        case = Case.query.get(case_id)
        jury_id = session.get("jury_id")
        # Проверяем, есть ли уже оценка для данного игрока и данного члена жюри
        existing_evaluation = Evaluation.query.filter_by(player_id=player.id, case_id=case.id, jury_id=jury_id).first()
        if player:
            if existing_evaluation:
                for criterion, score in zip(case.criteria, participant_scores):
                    existing_evaluation.update_evaluation(criterion.criteria_name, score)
            else:
                # Если оценки нет, создаем новую
                new_evaluation = Evaluation(player_id=player.id, case_id=case.id, points=0, jury_id=jury_id, criterion_scores=[])
                # Добавляем баллы за критерии
                for criterion, score in zip(case.criteria, participant_scores):
                    new_evaluation.add_criterion_score(criterion.criteria_name, score)
                # Сохраняем новый экземпляр в базу данных
                db.session.add(new_evaluation)
                total_score = new_evaluation.get_total_score()
                player.score = total_score
                new_evaluation.points = total_score
        db.session.commit()
        return redirect(url_for('participants'))


@app.route('/jury_participants_general_table')
def table():
    return render_template("obshaya_tablica1.html")


@app.route('/jury_teams')
def team():
    return render_template("comandsextend.html")


@app.route('/jury_№team')
def teamss():
    return render_template("dlyacom1.html")


@app.route('/jury_general_table_for_teams')
def tableteam():
    return render_template("comtablext.html")


@app.route('/results_for_participants')
def respart():
    return render_template("respart.html")


@app.route('/results_for_participant')
def respartconcrete():
    return render_template("part.html")


@app.route('/results_for_teams')
def resteam():
    return render_template("resteam.html")


@app.route('/results_for_team')
def resteamconcrete():
    return render_template("team.html")



if __name__ == "__main__":
    app.run(debug=True)

