# app_10.py

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash 
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user 
import os 

# 1. Flaskアプリケーションの初期化と設定
app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_strong_secret_key_here') 
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///board.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 2. SQLAlchemy（データベース）の初期化
db = SQLAlchemy(app)

# 3. Flask-Loginの初期化と設定
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 
login_manager.login_message = "ログインが必要です。"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# 4. データベースモデルの定義
# -----------------
# ★ Thread と Post モデルの定義 ★
# -----------------

class Thread(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    author = db.relationship('User', backref='threads', lazy=True)
    posts = db.relationship('Post', backref='thread', lazy='dynamic', cascade="all, delete-orphan")

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    thread_id = db.Column(db.Integer, db.ForeignKey('thread.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    author = db.relationship('User', backref='posts', lazy=True)

    def __repr__(self):
        return f'<Post {self.id}>'

class User(db.Model, UserMixin): 
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False) 

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

# 5. データベーステーブルの作成（モデル定義の直後で実行されます！）
# デプロイ時に新しいテーブル定義を強制的に反映させるための一時的なコードです。
with app.app_context():
    db.drop_all() 
    db.create_all()


# ----------------------------------------------------
# 認証関連のルーティング
# ----------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if db.session.execute(db.select(User).filter_by(username=username)).first():
            flash('そのユーザー名はすでに使われています。', 'error')
            return redirect(url_for('register'))

        new_user = User(username=username)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('登録が完了しました！ログインしてください。', 'success')
        return redirect(url_for('login'))
        
    return render_template('register_10.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = db.session.execute(db.select(User).filter_by(username=username)).scalar_one_or_none()
        
        if user and user.check_password(password):
            login_user(user) 
            flash('ログインしました。', 'success')
            return redirect(url_for('index'))
        else:
            flash('ユーザー名またはパスワードが違います。', 'error')
            
    return render_template('login_10.html')

@app.route('/logout')
@login_required 
def logout():
    logout_user() 
    flash('ログアウトしました。', 'success')
    return redirect(url_for('index'))


# ----------------------------------------------------
# 掲示板のルーティング (スレッド対応版)
# ----------------------------------------------------

# トップページ (スレッド一覧表示)
@app.route('/')
def index():
    # Threadモデルから一覧を取得
    threads = db.session.execute(db.select(Thread).order_by(Thread.created_at.desc())).scalars().all()
    
    # index_10.htmlでthreadsを受け取るようにHTML側の修正が必要です。
    return render_template('index_10.html', threads=threads) 

# 新規スレッド作成フォーム表示
@app.route('/create_thread')
@login_required 
def create_thread_form():
    # テンプレートファイルが必要です: thread_create_10.html 
    return render_template('thread_create_10.html')

# 新規スレッド作成処理 (Create)
@app.route('/create_thread', methods=['POST'])
@login_required 
def create_thread():
    title = request.form['title']
    content = request.form['content'] 
    
    if not title or not content:
        flash('タイトルと本文を入力してください。', 'error')
        return redirect(url_for('create_thread_form'))
    
    # 1. スレッド本体を作成
    new_thread = Thread(title=title, user_id=current_user.id)
    db.session.add(new_thread)
    db.session.commit() 

    # 2. スレッドの最初の投稿を作成 
    first_post = Post(content=content, thread_id=new_thread.id, user_id=current_user.id)
    db.session.add(first_post)
    db.session.commit()

    flash('新しいスレッドを作成しました。', 'success')
    return redirect(url_for('index'))


# ----------------------------------------------------
# 投稿関連の古いルーティング（一時的な措置）
# ----------------------------------------------------

# /post ルーティングは一時的にエラーを出すように変更
@app.route('/post', methods=['POST'])
@login_required 
def post_message():
    flash('エラー: スレッド機能に移行中のため、この投稿は現在使用できません。', 'error')
    return redirect(url_for('index'))

# 編集フォーム表示 (Update - フォーム表示)
@app.route('/edit/<int:id>')
@login_required 
def edit(id):
    post_to_edit = db.session.get(Post, id)
    if post_to_edit is None:
        abort(404)
    if post_to_edit.user_id != current_user.id:
        flash('他のユーザーの投稿は編集できません。', 'error')
        return redirect(url_for('index'))
        
    return render_template('edit_10.html', post=post_to_edit)

# データ更新処理 (Update - 実行)
@app.route('/update/<int:id>', methods=['POST'])
@login_required 
def update(id):
    post_to_update = db.session.get(Post, id)
    if post_to_update is None:
        abort(404)
    if post_to_update.user_id != current_user.id:
        flash('他のユーザーの投稿は更新できません。', 'error')
        return redirect(url_for('index'))
        
    new_content = request.form['content']
    post_to_update.content = new_content
    
    try:
        db.session.commit()
        flash('投稿を更新しました。', 'success')
        return redirect(url_for('index'))
    except:
        flash('投稿内容の更新中にエラーが発生しました', 'error')
        return redirect(url_for('index'))

# 削除処理 (Delete)
@app.route('/delete/<int:id>', methods=['POST'])
@login_required 
def delete(id):
    post_to_delete = db.session.get(Post, id)
    if post_to_delete is None:
        abort(404)
    if post_to_delete.user_id != current_user.id:
        flash('他のユーザーの投稿は削除できません。', 'error')
        return redirect(url_for('index'))

    try:
        db.session.delete(post_to_delete)
        db.session.commit()
        flash('投稿を削除しました。', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        print(f"削除エラー: {e}")
        flash('投稿の削除中にエラーが発生しました。', 'error')
        return redirect(url_for('index'))

# app_10.py (ファイルの最下部)
if __name__ == '__main__':
    pass