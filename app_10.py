# app_10.py

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash 
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user 
import os # 環境変数読み込み用

# 1. Flaskアプリケーションの初期化と設定
app = Flask(__name__)

# 環境変数からSECRET_KEYとDATABASE_URLを取得
# SECRET_KEYが設定されていない場合は、開発用の鍵を使用
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_strong_secret_key_here') 
# デプロイ先で設定されるDATABASE_URLを優先し、なければSQLiteを使用
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
    # LegacyAPIWarningを避けるため、get_or_404を使用するか、Session.get()を使用するのが望ましい
    return db.session.get(User, int(user_id))

# 4. データベースモデルの定義
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 投稿者IDを保存するカラムとUserモデルへのリレーションシップ
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    author = db.relationship('User', backref=db.backref('posts', lazy=True))

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

# 5. データベーステーブルの作成
# 開発環境でSQLiteを使うために残す（本番環境ではマイグレーションツール推奨）
with app.app_context():
    db.drop_all()  # 👈 古いテーブルを削除
    db.create_all() # 👈 新しい（サイズ256の）テーブルを作成


# ----------------------------------------------------
# 認証関連のルーティング
# ----------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # ユーザー名重複チェック
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
# 投稿関連のルーティング (本人確認ロジックを含む)
# ----------------------------------------------------

# トップページ (Read)
@app.route('/')
def index():
    posts = db.session.execute(db.select(Post).order_by(Post.id.desc())).scalars().all()
    return render_template('index_10.html', posts=posts) 

# 投稿処理 (Create)
@app.route('/post', methods=['POST'])
@login_required 
def post_message():
    post_content = request.form['content'] 
    
    # ログイン中のユーザーIDを保存
    new_post = Post(content=post_content, user_id=current_user.id)
    
    db.session.add(new_post)
    db.session.commit()

    flash('投稿が完了しました。', 'success')
    return redirect(url_for('index'))

# 編集フォーム表示 (Update - フォーム表示)
@app.route('/edit/<int:id>')
@login_required 
def edit(id):
    # 投稿が存在しない場合は404エラー
    post_to_edit = db.session.get(Post, id)
    if post_to_edit is None:
        abort(404)

    # ★本人確認ロジック：投稿者と現在のユーザーが一致しない場合はアクセス拒否
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
        
    # ★本人確認ロジック
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

    # ★本人確認ロジック
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

# app_10.py (ファイルの最下部に追加)

if __name__ == '__main__':
    import sys
    # RenderのbuildCommandで指定した 'db_init' フラグを受け取ったら実行
    if len(sys.argv) > 1 and sys.argv[1] == 'db_init':
        with app.app_context():
            db.create_all()
            print("Database tables created successfully by buildCommand!")
    else:
        # ローカルで通常起動する場合の処理があればここに記述
        # 例: app.run(debug=True)
        pass