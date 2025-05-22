import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- Database Setup ---
conn = sqlite3.connect('labourline.db', check_same_thread=False)
c = conn.cursor()

# Initialize tables
c.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    experience TEXT,
    gender TEXT,
    phone TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
)''')
c.execute('''CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER,
    receiver_id INTEGER,
    content TEXT,
    timestamp TEXT,
    FOREIGN KEY(sender_id) REFERENCES users(id),
    FOREIGN KEY(receiver_id) REFERENCES users(id)
)''')
c.execute('''CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    labourer_id INTEGER,
    rating INTEGER,
    comments TEXT,
    timestamp TEXT,
    FOREIGN KEY(customer_id) REFERENCES users(id),
    FOREIGN KEY(labourer_id) REFERENCES users(id)
)''')
conn.commit()

# --- Utility ---
def safe_rerun():
    if hasattr(st, 'experimental_rerun'):
        st.experimental_rerun()
    else:
        st.stop()

# --- Authentication ---
def signup():
    st.subheader('Sign Up')
    username = st.text_input('Username', key='signup_user')
    password = st.text_input('Password', type='password', key='signup_pass')
    role = st.selectbox('Role', ['customer', 'labourer'], key='signup_role')
    if st.button('Register', key='signup_btn'):
        if username and password:
            try:
                c.execute('INSERT INTO users (username,password,role) VALUES (?,?,?)',
                         (username,password,role))
                conn.commit()
                st.success('Registered! Please log in.')
            except sqlite3.IntegrityError:
                st.error('Username exists.')
        else:
            st.error('Provide both username and password.')

def login():
    st.subheader('Log In')
    username = st.text_input('Username', key='login_user')
    password = st.text_input('Password', type='password', key='login_pass')
    if st.button('Log In', key='login_btn'):
        c.execute('SELECT id,role FROM users WHERE username=? AND password=?',
                  (username,password))
        row = c.fetchone()
        if row:
            st.session_state['user'] = {'id':row[0],'username':username,'role':row[1]}
            safe_rerun()
        else:
            st.error('Invalid credentials.')

# --- Application ---
def main():
    st.set_page_config(page_title='LabourLine', layout='wide')
    if 'user' not in st.session_state:
        st.session_state['user'] = None

    if st.session_state['user'] is None:
        menu = st.sidebar.selectbox('Menu', ['Login','Sign Up'])
        if menu=='Login': login()
        else: signup()
        return

    user = st.session_state['user']
    st.sidebar.write(f"Logged in as: {user['username']} ({user['role']})")
    pages = ['Home','Profile','Chat','Feedback']
    if user['role']=='admin': pages.append('Admin')
    choice = st.sidebar.selectbox('Dashboard', pages)
    if st.sidebar.button('Logout'):
        st.session_state.pop('user')
        safe_rerun()

    if choice=='Home':
        st.header('Welcome to LabourLine')
        st.write('Navigate via sidebar.')

    elif choice=='Profile':
        if user['role']=='labourer':
            st.subheader('Your Profile')
            existing = c.execute('SELECT experience,gender,phone FROM profiles WHERE user_id=?',
                                 (user['id'],)).fetchone()
            if existing:
                exp,gend,phone = existing
                st.text(f'Experience: {exp}')
                st.text(f'Gender: {gend}')
                st.text(f'Phone: {phone}')
            exp = st.text_area('Work Experience')
            gender = st.selectbox('Gender',['Male','Female','Other'])
            phone = st.text_input('Phone')
            if st.button('Save', key='save_prof'):
                if existing:
                    c.execute('UPDATE profiles SET experience=?,gender=?,phone=? WHERE user_id=?',
                              (exp,gender,phone,user['id']))
                else:
                    c.execute('INSERT INTO profiles(user_id,experience,gender,phone) VALUES(?,?,?,?)',
                              (user['id'],exp,gender,phone))
                conn.commit()
                st.success('Profile updated.')
        else:
            st.error('Labourers only.')

    elif choice=='Chat':
        st.subheader('Chat')
        if user['role']=='customer':
            df = pd.read_sql('SELECT p.user_id,u.username FROM profiles p JOIN users u ON p.user_id=u.id',conn)
            if df.empty:
                st.info('No labourer profiles yet.')
            else:
                target = st.selectbox('Pick labourer',df['username'])
                target_id = df[df.username==target]['user_id'].iloc[0]
                if st.button('Open Chat', key='open_chat'):
                    st.session_state['chat_with']=target_id
                    safe_rerun()
        elif user['role']=='labourer':
            st.info('Waiting for customers to message you.')
        else:
            st.error('Customers only.')

        if 'chat_with' in st.session_state:
            partner = st.session_state['chat_with']
            hist = c.execute('''SELECT sender_id,content,timestamp FROM messages 
                               WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)
                               ORDER BY id''',
                             (user['id'],partner,partner,user['id'])).fetchall()
            for s,txt,ts in hist:
                label = 'You' if s==user['id'] else 'Them'
                st.write(f"**{label}** ({ts}): {txt}")
            msg = st.text_input('Message', key='msg_input')
            if st.button('Send', key='send_btn') and msg:
                now = datetime.now().strftime('%Y-%m-%d %H:%M')
                c.execute('INSERT INTO messages(sender_id,receiver_id,content,timestamp) VALUES(?,?,?,?)',
                          (user['id'],partner,msg,now))
                conn.commit()
                safe_rerun()

    elif choice=='Feedback':
        if user['role']=='customer':
            st.subheader('Leave Feedback')
            fb = pd.read_sql('SELECT u2.id,u2.username FROM feedback f JOIN users u2 ON f.labourer_id=u2.id',conn)
            labourer = st.selectbox('Labourer',[user for _,user in fb.values] if not fb.empty else [])
            rating = st.slider('Rating',1,5)
            comment = st.text_area('Comments')
            if st.button('Submit', key='fb_btn'):
                ts = datetime.now().strftime('%Y-%m-%d')
                lid = fb[fb.username==labourer].id.iloc[0]
                c.execute('INSERT INTO feedback(customer_id,labourer_id,rating,comments,timestamp) VALUES(?,?,?,?,?)',
                          (user['id'],lid,rating,comment,ts))
                conn.commit()
                st.success('Thank you!')
        else:
            st.error('Customers only.')

    elif choice=='Admin':
        if user['role']=='admin':
            st.subheader('Admin Panel')
            us = pd.read_sql('SELECT id,username,role FROM users',conn)
            st.dataframe(us)
            rem = st.text_input('User ID to remove')
            if st.button('Remove', key='rem_btn') and rem.isdigit():
                c.execute('DELETE FROM users WHERE id=?',(int(rem),))
                conn.commit()
                st.success('Removed.')
            fb_all = pd.read_sql('SELECT customer_id,labourer_id,rating,comments,timestamp FROM feedback',conn)
            st.dataframe(fb_all)
        else:
            st.error('Admins only.')

if __name__=='__main__':
    main()
