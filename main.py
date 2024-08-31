import os
from flask import Flask, request, render_template, redirect, session, url_for, g, send_file
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from collections import defaultdict
from io import BytesIO

app = Flask(__name__)
app.config["SECRET_KEY"] = "aofl-29ri-sd93-foi2-fin2-f92h-0xo3-42ts-i3nf-dowj-193d-f93h-sll3"

CLIENT_ID = "7b2949c814ee42559eca35bf50859edb"
CLIENT_SECRET = "bf273ba2762b4b04a6ac7a8dcb938102"
REDIRECT_URI = "https://playlistr-app-production.up.railway.app/callback"
SCOPE = "user-library-read, playlist-modify-private, playlist-modify-public"

cache_handler = FlaskSessionCacheHandler(session)

sp_oauth = SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE,
    cache_handler=cache_handler,
    show_dialog=True
)

USER_SONG_IDS = {}

sp = Spotify(auth_manager=sp_oauth)


@app.route("/")
def home():
    return render_template("home.html")

@app.route("/btn")
def btn():
    return redirect(url_for("authorize"))


@app.route("/authorize")
def authorize():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        #callback is called once authenticated
        return redirect(auth_url)
    #return render_template()
    #Already authenticated? then do this:
    return redirect(url_for("dashboard"))

@app.route("/callback")
def callback():
    sp_oauth.get_access_token(request.args["code"])
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():


    name = sp.current_user()["display_name"]

    USER_SONG_IDS[sp.current_user()["id"]] = get_ids()
    num = len(USER_SONG_IDS[sp.current_user()["id"]])

    return render_template("dashboard.html", name=name, num=num)


@app.route("/get_liked_songs")
def get_liked_songs():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    
    return get_song_features(get_ids())



@app.route("/ids")
def ids():
    song_features = get_song_features(USER_SONG_IDS[sp.current_user()["id"]])
    df = get_df(song_features)

    #csv = df.to_csv()

    csv_data = BytesIO()
    df.to_csv(csv_data, index=False)
    csv_data.seek(0)

    # Serve the CSV as a file download
    return send_file(csv_data, mimetype='text/csv', as_attachment=True, download_name="song_features.csv")


@app.route("/run_alg")
def run_alg():
    data = get_df(get_song_features(get_ids()))
    ids = data[["id"]]
    data = data.drop(["key", "mode", "time_signature", "id"], axis=1)


    scaler = StandardScaler()
    data_normalized = pd.DataFrame(scaler.fit_transform(data), columns=data.columns)
    kmeans = KMeans(n_clusters=4, random_state=0)

    kmeans.fit(data_normalized)
    ids["group"] = kmeans.predict(data_normalized)
    ids = ids.to_numpy()

    
    dict = defaultdict(list)
    for item in ids.to_numpy():
        dict[item[1]].append(item[0])

    """dict = {}
    for item in ids:
        key = item[1]
        value = item[0]

        if key in dict:
            dict[key].append(value)
        else:
            dict[key] = [value]"""

    user_id = sp.current_user()["id"]
    for playlist_num in range(4):
        curr_playlist = sp.user_playlist_create(user=user_id, name=f"PLAYLISTR {playlist_num + 1}")
        sp.user_playlist_add_tracks(user=user_id, playlist_id=curr_playlist["id"], tracks=dict[playlist_num])

    return render_template("done.html")



    
    

    
@app.route("/logout")
def logout():
    session.clear()

    return redirect(url_for("home"))


# Returns a list of the song IDs in "liked songs"
# Each ID is a string
def get_ids():
    offset = 0
    ids = []
    while True:
        batch = sp.current_user_saved_tracks(limit=50, offset=offset)
        for song in range(len(batch["items"])):
            ids.append(batch["items"][song]["track"]["id"])
        if batch["next"] is not None:
            offset += 50
        else:
            break

    return ids


# Returns a list of dictionaries
# Each dictionary corresponds to a song
def get_song_features(ids):
    starting_idx = 0
    audio_features = []
    while starting_idx < len(ids):
        sp.audio_features(ids[starting_idx:starting_idx+100])

        audio_features += sp.audio_features(ids[starting_idx:starting_idx+100])
        starting_idx += 100

    return audio_features

def get_df(audio_features):
    features_list = []
    for features in audio_features:
        features_list.append([features["id"],
                            features["danceability"],
                            features["energy"],
                            features["key"],
                            features["loudness"],
                            features["mode"],
                            features["speechiness"],
                            features["acousticness"],
                            features["instrumentalness"],
                            features["liveness"],
                            features["valence"],
                            features["tempo"],
                            features["time_signature"]
                            ])
        
    data = pd.DataFrame(features_list, columns=["id",
                                                "danceability",
                                                "energy",
                                                "key",
                                                "loudness",
                                                "mode",
                                                "speechiness",
                                                "acousticness",
                                                "instrumentalness",
                                                "liveness",
                                                "valence",
                                                "tempo",
                                                "time_signature"])
    
    return data





if __name__ == "__main__":
    app.run(debug=True, port=os.getenv("PORT", default=5000))

