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

class Thread(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    author = db.relationship('User', backref='threads', lazy=True)
    # cascade="all, delete-orphan" により、スレッド削除時に投稿も自動削除
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
# 掲示板のルーティング
# ----------------------------------------------------

# トップページ (スレッド一覧表示)
@app.route('/')
def index():
    threads = db.session.execute(db.select(Thread).order_by(Thread.created_at.desc())).scalars().all()
    return render_template('index_10.html', threads=threads) 

# 新規スレッド作成フォーム表示
@app.route('/create_thread')
@login_required 
def create_thread_form():
    return render_template('thread_create_10.html')

# 新規スレッド作成処理
@app.route('/create_thread', methods=['POST'])
@login_required 
def create_thread():
    title = request.form['title']
    content = request.form['content'] 
    
    if not title or not content:
        flash('タイトルと本文を入力してください。', 'error')
        return redirect(url_for('create_thread_form'))
    
    new_thread = Thread(title=title, user_id=current_user.id)
    db.session.add(new_thread)
    db.session.commit() 

    first_post = Post(content=content, thread_id=new_thread.id, user_id=current_user.id)
    db.session.add(first_post)
    db.session.commit()

    flash('新しいスレッドを作成しました。', 'success')
    return redirect(url_for('index'))

# スレッド詳細表示
@app.route('/thread/<int:thread_id>')
def thread_detail(thread_id):
    thread = db.session.get(Thread, thread_id)
    if thread is None:
        abort(404)
        
    posts = db.session.execute(
        db.select(Post)
        .filter_by(thread_id=thread_id)
        .order_by(Post.created_at.asc())
    ).scalars().all()
    
    return render_template('thread_detail_10.html', thread=thread, posts=posts)

# スレッドへの返信処理
@app.route('/post_to_thread/<int:thread_id>', methods=['POST'])
@login_required
def post_to_thread(thread_id):
    thread = db.session.get(Thread, thread_id)
    if thread is None:
        abort(404)
        
    content = request.form['content']
    if not content:
        flash('本文を入力してください。', 'error')
        return redirect(url_for('thread_detail', thread_id=thread_id))

    new_post = Post(content=content, thread_id=thread_id, user_id=current_user.id)
    db.session.add(new_post)
    
    try:
        db.session.commit()
        flash('投稿が完了しました。', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"データベースエラー: {e}")
        flash('投稿中に予期せぬエラーが発生しました。', 'error')
        
    return redirect(url_for('thread_detail', thread_id=thread_id))

# 投稿編集フォーム (Update - Form)
@app.route('/edit/<int:id>')
@login_required 
def edit(id):
    post_to_edit = db.session.get(Post, id)
    if post_to_edit is None:
        abort(404)
    if post_to_edit.user_id != current_user.id:
        flash('他のユーザーの投稿は編集できません。', 'error')
        return redirect(url_for('thread_detail', thread_id=post_to_edit.thread_id))
        
    return render_template('edit_10.html', post=post_to_edit)

# データ更新処理 (Update - Action)
@app.route('/update/<int:id>', methods=['POST'])
@login_required 
def update(id):
    post_to_update = db.session.get(Post, id)
    if post_to_update is None:
        abort(404)
    if post_to_update.user_id != current_user.id:
        flash('他のユーザーの投稿は更新できません。', 'error')
        return redirect(url_for('thread_detail', thread_id=post_to_update.thread_id))
        
    new_content = request.form['content']
    post_to_update.content = new_content
    
    try:
        db.session.commit()
        flash('投稿を更新しました。', 'success')
        return redirect(url_for('thread_detail', thread_id=post_to_update.thread_id))
    except:
        flash('更新中にエラーが発生しました', 'error')
        return redirect(url_for('thread_detail', thread_id=post_to_update.thread_id))

# ★ 削除処理 (Delete - Modified for Threads) ★
@app.route('/delete/<int:id>') # GETリクエストで動作するようにしています（ボタンのリンク）
@login_required 
def delete(id):
    post_to_delete = db.session.get(Post, id)
    
    if post_to_delete is None:
        flash('削除対象の投稿が見つかりませんでした。', 'error')
        return redirect(url_for('index'))

    # ユーザー認証
    if post_to_delete.user_id != current_user.id:
        flash('他のユーザーの投稿は削除できません。', 'error')
        return redirect(url_for('thread_detail', thread_id=post_to_delete.thread_id))

    thread_id = post_to_delete.thread_id
    
    try:
        # もしこの投稿が「スレッドの最初の投稿」だった場合、スレッドごと削除する
        # （スレッドの最初の投稿を取得して比較）
        first_post = db.session.execute(
            db.select(Post).filter_by(thread_id=thread_id).order_by(Post.created_at.asc())
        ).scalars().first()

        if post_to_delete.id == first_post.id:
            # スレッドの持ち主（最初の投稿者）が削除する場合、スレッド自体を削除
            thread_to_delete = db.session.get(Thread, thread_id)
            db.session.delete(thread_to_delete)
            db.session.commit()
            flash('スレッド全体が削除されました。', 'success')
            return redirect(url_for('index'))
        else:
            # 通常のレス削除
            db.session.delete(post_to_delete)
            db.session.commit()
            flash('投稿を削除しました。', 'success')
            return redirect(url_for('thread_detail', thread_id=thread_id))
        
    except Exception as e:
        db.session.rollback()
        print(f"削除エラー: {e}")
        flash(f'削除中にエラーが発生しました。', 'error')
        return redirect(url_for('thread_detail', thread_id=thread_id))

if __name__ == '__main__':
    pass