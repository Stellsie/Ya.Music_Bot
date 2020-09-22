import asyncio
import os
import configparser
import discord
import yandex_music
from random import shuffle
from discord.ext import commands
from yandex_music.client import Client

ffmpeg_options = {
    'options': '-vn'
}

cfg = configparser.ConfigParser()
cfg.read('config.ini')


def search_for(ctx, query):
    q = str(query)
    q_types = ['track', 'album', 'artist', 'playlist']
    q_type = None
    for i in q_types:
        if q.find(i) != -1:
            if q_type is None:
                q_type = i
                q.replace(i, '')
            else:
                ctx.send('В запросе найдено больше одного типа, используется первый найденный')
                q.replace(i, '')
    if q_type == 'track':
        result = client.search(text=q, type_=q_type).tracks.results
    elif q_type == 'album':
        result = client.search(text=q, type_=q_type).albums.results
    elif q_type == 'artist':
        result = client.search(text=q, type_=q_type).artists.results
    elif q_type == 'playlist':
        result = client.search(text=q, type_=q_type).playlists.results
    # not working now :(
    # elif q_type == 'podcasts':
    #     result = client.search(text=q, type_=q_type).podcasts
    else:  # if query type not specified, searching tracks
        result = client.search(text=q, type_='track').tracks.results
    return result


class TracksQueue:
    def __init__(self):
        self.queue = []

    def put(self, item):
        self.queue += item

    def get(self):
        item = self.queue.pop(0)
        if type(item) == yandex_music.TrackShort:
            return item.track
        elif type(item) == yandex_music.Track:
            return item
        else:
            return None

    def empty(self):
        return len(self.queue) == 0 if True else False

    def shuffle(self):
        shuffle(self.queue)

    def print_tracks(self):
        if self.empty():
            message = 'Очередь пуста'
        else:
            message = 'Сейчас в очереди: \n'
            index = 0
            items_count = len(self.queue)
            while index < 10 and index < items_count:
                if type(self.queue[index]) == yandex_music.Track:
                    message += str(index + 1) + ': ' + self.queue[index].title + ' - ' \
                               + get_artists(self.queue[index]) + '\n'
                    index += 1
                elif type(self.queue[index]) == yandex_music.TrackShort:
                    message += str(index + 1) + ': ' + self.queue[index].track.title + ' - ' \
                               + get_artists(self.queue[index].track) + '\n'
                    index += 1
            if items_count > 10:
                message += 'И еще {} треков'.format((items_count - 10))
        return message


tracks_queue = TracksQueue()


def get_track_path(track: yandex_music.Track):
    track_path = './tracks/' + str(track.trackId) + '.mp3'
    track_path = track_path.replace(':', '')
    if not os.path.isfile(track_path):
        print('Download started: {}'.format(track_path))
        track.download(track_path)
        print('Download finished')
    else:
        print('Track already in {}'.format(track_path))
    return track_path


def get_artists(track):
    artists = ''
    for i in range(len(track.artists)):
        if i > 0:
            artists += ', '
        artists += track.artists[i].name
    return artists


class Music(commands.Cog):
    def __init__(self, _bot):
        self.bot = _bot

    @commands.command()
    async def join(self, ctx, *, channel: discord.VoiceChannel):
        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)
        await channel.connect()

    # TODO: Search
    # @commands.command()
    # async def search(self, ctx, *, query_type, query):

    @commands.command()
    async def play(self, ctx, *, query=None):
        if query is None:
            await ctx.send('Попытка продолжить воспроизведение из очереди...')
            if ctx.voice_client.is_playing():
                await ctx.send('Плеер уже играет!')
            elif tracks_queue.empty():
                await asyncio.sleep(3)  # делаем вид, что что-то делаем :D
                await ctx.send('Очередь пуста!')
            await ctx.send('Чтобы добавить музыку в очередь, добавьте название '
                           'трека/плейлиста/альбома или имя испольнителя и укажите тип запроса — '
                           'track, album, playlist или artist (необязательно, по умолчанию track) и текст запроса.')
        else:
            result = search_for(ctx, query)[0]
            if type(result) == yandex_music.Track:
                await ctx.send('Трек {} - {} добавлен в очередь'.format(result.title, get_artists(result)))
                tracks_queue.put(result)
            elif type(result) == yandex_music.Album:
                await ctx.send('Альбом {} - {} добавлен в очередь'.format(result.title, get_artists(result)))
                tracks_queue.put(client.albums_with_tracks(album_id=result.id).volumes[0])
            elif type(result) == yandex_music.Playlist:
                await ctx.send('Плейлист "{}" добавлен в очередь'.format(result.title))
                tracks_queue.put(client.usersPlaylists(kind=result.kind, user_id=result.owner.uid)[0].tracks)
            elif type(result) == yandex_music.Artist:
                await ctx.send('10 популярных треков исполнителя {} добавлены в очередь'.format(result.name))
                tracks_queue.put(result.getTracks().tracks[:10])
        while ctx.voice_client.is_playing():
            await asyncio.sleep(1)

    @commands.command()
    async def volume(self, ctx, volume: int):
        if ctx.voice_client is None:
            return await ctx.send("Не подключен к голосовому каналу.")
        ctx.voice_client.source.volume = volume / 100
        await ctx.send("Громкость установлена на {}%".format(volume))

    @commands.command()
    async def skip(self, ctx):
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send(':next_track:')
            await self.play_queue(ctx)

        else:
            await ctx.send('Плеер не играет')

    @commands.command()
    async def queue(self, ctx):
        await ctx.send(tracks_queue.print_tracks())

    @commands.command()
    async def shuffle(self, ctx):
        if not tracks_queue.empty():
            tracks_queue.shuffle()
            await ctx.send('Очередь перемешана')
        else:
            await ctx.send('Очередь пуста!')

    @commands.command()
    async def stop(self, ctx):
        await ctx.voice_client.disconnect()

    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("Вы не подключены к голосовому каналу.")
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()

    @play.after_invoke
    async def play_queue(self, ctx):
        while tracks_queue.empty():
            await asyncio.sleep(1)
            print('wait for tracks...')
        while not tracks_queue.empty():
            track = tracks_queue.get()
            track_path = get_track_path(track)
            track_name = track.title + ' - ' + get_artists(track)
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(track_path))
            ctx.voice_client.play(source, after=lambda e: print('Player error: %s' % e) if e else None)

            message = await ctx.send('Сейчас играет: {}'.format(track_name))
            while ctx.voice_client.is_playing():
                await asyncio.sleep(1)
            await message.delete()


bot = commands.Bot(command_prefix=commands.when_mentioned_or("m."),
                   description='Relatively simple music bot example')


@bot.event
async def on_ready():
    print('Logged in as {0} ({0.id})'.format(bot.user))
    print('------')

if cfg['YANDEX'].getboolean('use_token'):
    client = Client(cfg['YANDEX']['token'])
else:
    client = Client.from_credentials(cfg['YANDEX']['login'], cfg['YANDEX']['password'])
bot.add_cog(Music(bot))
bot.run(cfg['DISCORD']['token'])
