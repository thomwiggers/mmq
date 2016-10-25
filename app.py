from __future__ import print_function, unicode_literals

from flask import Flask, render_template, request, jsonify
from flask.ext.sqlalchemy import SQLAlchemy
from  sqlalchemy.sql.expression import func
import time
import json
import random
from oauth2client.tools import argparser
from apiclient.discovery import build
import re


# Set DEVELOPER_KEY to the API key value from the APIs & auth > Registered apps
# tab of
#   https://cloud.google.com/console
# Please ensure that you have enabled the YouTube Data API for your project.
DEVELOPER_KEY = "REPLACE_ME"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


#################
# configuration #
#################
if __name__ == '__main__':
    print("This is not how you should run this application. ")
    print("Try python manage.py runserver")
    exit()

app = Flask(__name__)
app.debug = True
db = SQLAlchemy(app)

from models import Channel, Record, Video

##########
# routes #
##########
@app.route('/<channel_slug>', methods=['GET', 'POST'])
def channelindex(channel_slug):
    channel = Channel.query.filter_by(slug=channel_slug).first()
    if not channel:
        return jsonify({"msg": "notfound"})
    records = db.session.query(func.count(Record.id).label('aantal'),Video.id.label('id'), Video.code.label('code'), Video.title.label('title'), Video.duration.label('duration')).filter(Record.channel_id==channel.id).join(Video).group_by(Video.id).all()
    return render_template('channelindex.html', channel=channel, records=records)


@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@app.route('/channels', methods=['GET', 'POST'])
def channels():
    channels = Channel.query.filter_by(active=True).all()
    return jsonify({"channels" : [{'title' :x.title, 'slug': x.slug}
                                  for x in channels]})

@app.route('/add', methods=['POST'])
def addchannel():
    data = json.loads(request.data.decode())
    title = data["title"]
    errors = []
    try:
        channel = Channel(title)
        db.session.add(channel)
        db.session.commit()
        return jsonify({"succes": True})
    except Exception as e:
        errors.append("Unable to add channel to database. %s " %  e)
        return jsonify({"error": errors})

def queue_video(channel_slug, id, title, duration):
    errors = []
    if len(id) != 11:
        errors.append("Add a youtube id not a link.")
        return jsonify({"error": errors})
    channel = Channel.query.filter_by(slug=channel_slug).first()
    if not channel:
        return jsonify({"msg": "Channel not found"})
    # see if video exists if it doesnt make a new one
    video = Video.query.filter_by(code=id).first()
    if not video:
        video = Video(id, title=title,duration=duration)
        db.session.add(video)
        db.session.commit()
    try:
        record = Record(channel.id , video.id)
        channel.update_id = channel.update_id + 1
        db.session.add(record)
        db.session.commit()
        return jsonify({"succes": True})
    except Exception as e:
        errors.append("Unable to add item to database: %s" % e)
        return jsonify({"errors": errors})


@app.route('/<channel_slug>/add', methods=['POST'])
def add(channel_slug):
    data = json.loads(request.data.decode())
    id = data["id"]
    errors = []
    if len(id) != 11:
        errors.append("Add a youtube id not a link.")
        return jsonify({"error": errors})

    channel = Channel.query.filter_by(slug=channel_slug).first()
    if not channel:
        return jsonify({"msg": "notfound"})

    # see if video exists if it doesnt make a new one
    video = Video.query.filter_by(code=id).first()
    if not video:
        title = data["title"]
        duration = data["duration"]
        video = Video(id, title=title,duration=duration)
        db.session.add(video)
        db.session.commit()
    try:
        record = Record(channel.id , video.id)
        channel.update_id = channel.update_id + 1
        db.session.add(record)
        db.session.commit()
        return jsonify({"succes": True})
    except Exception as e:
        errors.append("Unable to add item to database. %s" % e)
        return jsonify({"error": errors})

@app.route('/<channel_slug>/finish', methods=['POST'])
def finish_command(channel_slug):
    channel = Channel.query.filter_by(slug=channel_slug).first()
    if not channel:
        return jsonify({"msg": "notfound"})
    data=request.get_json()
    if 'id' not in data:
        return jsonify({'succes':False, "message" : "Geen valide post request"})

    record = Record.query.filter_by(id=data['id'],channel_id=channel.id).first()
    if not record:
        return "404 - Not found"
    channel.update_id = channel.update_id + 1
    record.finish()
    db.session.commit()
    return jsonify({"succes":True})

@app.route('/<channel_slug>/remove', methods=['POST'])
def remove_command(channel_slug):
    channel = Channel.query.filter_by(slug=channel_slug).first()
    if not channel:
        return jsonify({"msg": "notfound"})
    data=request.get_json()
    if 'id' not in data:
        return jsonify({'succes':False, "message" : "Geen valide post request"})
    record = Record.query.filter_by(id=data['id'],channel_id=channel.id).first()
    channel.update_id = channel.update_id + 1
    db.session.delete(record)
    db.session.commit()
    return jsonify({"succes":True})

@app.route("/<channel_slug>/set/volume", methods=['POST'])
def set_volume(channel_slug):
    channel = Channel.query.filter_by(slug=channel_slug).first()
    if not channel:
        return jsonify({"msg": "notfound"})
    data=request.get_json()
    if 'vol' not in data:
        return jsonify({'succes':False, "message" : "Geen valide post request"})
    if int(data['vol']) > 0 and int(data['vol']) < 101:
        channel.update_id = channel.update_id + 1
        channel.volume = int(data['vol'])
        db.session.commit()
    return jsonify({"succes":True})

@app.route("/<channel_slug>/send/update", methods=['POST', 'GET'])
def send_update(channel_slug):
    channel = Channel.query.filter_by(slug=channel_slug).first()
    if not channel:
        return jsonify({'fail':'Channel not found'})
    if channel.update == 0:
        channel.update = 1
        channel.update_id += 1
        db.session.commit()
        return jsonify({'succes':"Doot doot"})
    return jsonify({'failed':'doot doot not allowed :(. To unlock this feature send me an email.'})

@app.route("/<channel_slug>/ack/update", methods=['POST', 'GET'])
def received_update(channel_slug):
    channel = Channel.query.filter_by(slug=channel_slug).first()
    if not channel:
        return jsonify({'fail':'Channel not found'})
    if channel.update == 1:
        channel.update = 0
        db.session.commit()
        return jsonify({'succes':'einde doot doot'})
    return jsonify({'failed':'doot doots are blocked :(. To unlock this feature send me an email.'})

@app.route("/<channel_slug>/add_favorite", methods=['POST'])
def add_favorite(channel_slug):
    channel = Channel.query.filter_by(slug=channel_slug).first()
    if not channel:
        return jsonify({'fail':'Channel not found'})

    data=request.get_json()
    if 'v_id' not in data:
        return jsonify({'succes':False, "message" : "Geen valide post request"})
    video = Video.query.get(data['v_id'])
    if not video:
        return jsonify({'succes':False, "message" : "Geen valide post request"})
    channel.favorites.append(video)
    channel.update_id = channel.update_id + 1
    db.session.commit()
    return jsonify({"succes":True})

def YTDurationToSeconds(duration):
  match = re.match('PT(\d+H)?(\d+M)?(\d+S)?', duration).groups()
  hours = _js_parseInt(match[0]) if match[0] else 0
  minutes = _js_parseInt(match[1]) if match[1] else 0
  seconds = _js_parseInt(match[2]) if match[2] else 0
  return hours * 3600 + minutes * 60 + seconds

# js-like parseInt
# https://gist.github.com/douglasmiranda/2174255
def _js_parseInt(string):
    return int(''.join([x for x in string if x.isdigit()]))

@app.route("/<channel_slug>/feeling_lucky/<query>")
def feeling_lucky(channel_slug, query):
    channel = Channel.query.filter_by(slug=channel_slug).first()
    if not channel:
        return jsonify({'fail':'Channel not found'})
    if not query:
        return jsonify({'fail':'Empty search query'})
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
    developerKey=DEVELOPER_KEY)
    # Call the search.list method to retrieve results matching the specified
    # query term.
    search_response = youtube.search().list(
       q=query,
       type="video",
       part="id,snippet",
       maxResults=1
    ).execute()

    try:
        videoId = search_response['items'][0]['id']['videoId']
    except:
        return jsonify({'succes':False, "message" : "Geen video gevonden"})

    contentDetails = youtube.videos().list(
         id=videoId,
         part = 'contentDetails'
    ).execute()
    queue_video(channel_slug, search_response['items'][0]['id']['videoId'], search_response['items'][0]['snippet']['title'], YTDurationToSeconds(contentDetails['items'][0]['contentDetails']['duration']))
    return jsonify({'succes': True})

@app.route("/<channel_slug>/remove_favorite", methods=['POST'])
def remove_favorite(channel_slug):
    channel = Channel.query.filter_by(slug=channel_slug).first()
    if not channel:
        return jsonify({'fail':'Channel not found'})

    data=request.get_json()
    if 'v_id' not in data:
        return jsonify({'succes':False, "message" : "Geen valide post request"})
    video = Video.query.get(data['v_id'])
    if not video:
        return jsonify({'succes':False, "message" : "Geen valide post request"})
    channel.favorites.remove(video)
    channel.update_id = channel.update_id + 1
    db.session.commit()
    return jsonify({"succes":True})

@app.route("/<channel_slug>/playlist", methods=['POST'])
def get_playlist(channel_slug):
    channel = Channel.query.filter_by(slug=channel_slug).first()
    postdata = request.get_json()
    if not channel:
        return jsonify({"error" : "404 - Not found"})
    for i in range(1000):
        if 'update_id' in postdata and postdata['update_id'] < channel.update_id:
            q = Record.query.filter_by(channel_id=channel.id, executed=True).order_by(Record.id.desc()).limit(20)
            results = Record.query.filter_by(executed=False,channel_id=channel.id).all()
            if not results:
                if len(channel.favorites) != 0:
                    rand = random.randrange(0, len(channel.favorites))
                    random_rec = channel.favorites[rand]
                    if random_rec:
                        entry = Record(channel.id, random_rec.id)
                        channel.update_id += 1
                        db.session.add(entry)
                        db.session.commit()
                        results = [entry]
                else:
                    random_rec_q = Record.query.filter_by(channel_id=channel.id)
                    rand = random.randrange(0, random_rec_q.count())
                    random_rec = random_rec_q.all()[rand]
                    if random_rec:
                        entry = Record(channel.id, random_rec.video.id)
                        channel.update_id += 1
                        db.session.add(entry)
                        db.session.commit()
                        results = [entry]
            current = Record.query.filter_by(executed=True, channel_id=channel.id).order_by(Record.id.desc()).first()
            data = {
                "playlistVideos" : [{'code' :x.video.code,'title':x.video.title, "id":x.video.id, "favorite": x.video in channel.favorites} for x in q],
                "upcoming" : [{'code' :x.video.code, 'r_id': x.id, 'title':x.video.title, 'duration': x.video.duration, 'id':x.video.id, "favorite": x.video in channel.favorites} for x in results],
                "volume" : channel.volume,
                "update_id" : channel.update_id,
                "update" : channel.update
            }
            if current:
                data['current_title'] = current.video.title
            else:
                data['current_title'] = "no playback detected"
            return jsonify(data)
        db.session.commit()
        channel = Channel.query.filter_by(slug=channel_slug).first()
        time.sleep(0.05)
    return jsonify({'update_id':channel.update_id})

@app.route("/<channel_slug>/upcoming", methods=['POST','GET'])
def get_upcoming(channel_slug):
    channel = Channel.query.filter_by(slug=channel_slug).first()
    if not channel:
        return jsonify({"error" : "404 - Not found"})
    q = Record.query.filter_by(channel_id=channel.id,
                               executed=True).order_by(Record.id.desc()).limit(20)
    results = Record.query.filter_by(executed=False,channel_id=channel.id).all()
    if not results:
        if len(channel.favorites) != 0:
            rand = random.randrange(0, len(channel.favorites))
            random_rec = channel.favorites[rand]
            if random_rec:
                entry = Record(channel.id, random_rec.id)
                channel.update_id += 1
                db.session.add(entry)
                db.session.commit()
                results = [entry]
        else:
            random_rec_q = Record.query.filter_by(channel_id=channel.id)
            rand = random.randrange(0, random_rec_q.count())
            random_rec = random_rec_q.all()[rand]
            if random_rec:
                entry = Record(channel.id, random_rec.video.id)
                channel.update_id += 1
                db.session.add(entry)
                db.session.commit()
                results = [entry]
    current = Record.query.filter_by(executed=True, channel_id=channel.id).order_by(Record.id.desc()).first()
    data = {
        "upcoming" : [{'code' :x.video.code, 'r_id': x.id, 'title':x.video.title, 'duration': x.video.duration, 'id':x.video.id, "favorite": x.video in channel.favorites} for x in results],
        "volume" : channel.volume,
    }
    if current:
        data['current_title'] = current.video.title
    else:
        data['current_title'] = "no playback detected"
    return jsonify(data)
