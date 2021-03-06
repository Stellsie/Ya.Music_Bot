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


def print_track_list(t_list):
    message = ''
    index = 0
    items_count = len(t_list)
    while index < 10 and index < items_count:
        if type(t_list[index]) == yandex_music.Track:
            message += str(index + 1) + ': ' + t_list[index].title + ' - ' \
                       + get_artists(t_list[index]) + '\n'
            index += 1
        elif type(t_list[index]) == yandex_music.TrackShort:
            message += str(index + 1) + ': ' + t_list[index].track.title + ' - ' \
                       + get_artists(t_list[index].track) + '\n'
            index += 1
        elif type(t_list[index]) == yandex_music.BlockEntity:
            message += str(index + 1) + ': ' + t_list[index].data.track.title + ' - ' \
                       + get_artists(t_list[index].data.track) + '\n'
            index += 1
    if items_count > 10:
        message += 'И еще {} треков'.format((items_count - 10))
    return message


def search_for(keyword, query):
    q = str(query)
    keyword = str(keyword)
    q_keyword = None
    q_keywords = ['track', 'album', 'artist', 'playlist', 'chart', 'чарт', 'likes']
    for i in q_keywords:
        if keyword.find(i) != -1:
            q_keyword = i
    if q_keyword is None:
        q_keyword = 'all'
        q = keyword + ' ' + q
    if q_keyword == 'чарт' or q_keyword == 'chart':
        return client.landing(blocks='chart')
    elif q_keyword == 'likes':
        return client.users_likes_tracks(user_id=q)
    search = client.search(text=q, type_=q_keyword)
    if search is not None:
        if q_keyword == 'track':
            return search.tracks.results
        elif q_keyword == 'album':
            return search.albums.results
        elif q_keyword == 'artist':
            return search.artists.results
        elif q_keyword == 'playlist':
            return search.playlists.results
        elif q_keyword == 'all':
            return search.best
    else:
        return None


class TracksQueue:
    def __init__(self):
        self.queue = []

    def put(self, item):
        self.queue += item

    def get(self):
        item = self.queue.pop(0)
        if type(item) == yandex_music.Track:
            return item
        elif type(item) == yandex_music.TrackShort:
            return item.track
        elif type(item) == yandex_music.BlockEntity:
            return item.data.track
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
            message += print_track_list(self.queue)
        return message

    def clear(self):
        self.queue.clear()


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


async def play_queue(ctx):
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
    async def play(self, ctx, keyword=None, *, query=None):
        if keyword is None:
            await ctx.send('Попытка продолжить воспроизведение из очереди...')
            if ctx.voice_client.is_playing():
                await ctx.send('Плеер уже играет!')
            elif tracks_queue.empty():
                await asyncio.sleep(3)  # делаем вид, что что-то делаем :D
                await ctx.send('Очередь пуста!')
            else:
                await play_queue(ctx)
            await ctx.send('Чтобы добавить музыку в очередь, добавьте название '
                           'трека/плейлиста/альбома или имя испольнителя и укажите тип запроса — '
                           'track, album, playlist или artist (необязательно, по умолчанию track) и текст запроса.')
        else:
            result = search_for(keyword, query)
            if type(result) != yandex_music.TracksList and type(result) != yandex_music.Best:
                result = result[0]
            if result is not None:
                if type(result) == yandex_music.Best:
                    result = result.result
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
                    tracks_queue.put(result.get_tracks(page_size=10).tracks)
                elif type(result) == yandex_music.Block:
                    await ctx.send('В очередь добавлены 10 первых треков чарта')
                    tracks_queue.put(result.entities)
                elif type(result) == yandex_music.TracksList:
                    await ctx.send('В очередь добавлены понравившиеся треки')
                    tracks_queue.put(result.tracks)
                while ctx.voice_client.is_playing():
                    await asyncio.sleep(1)
                await play_queue(ctx)
            else:
                await ctx.send('Ничего не найдено :(')

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
            await play_queue(ctx)

        else:
            await ctx.send('Плеер не играет')

    @commands.command()
    async def queue(self, ctx):
        await ctx.send(tracks_queue.print_tracks())

    @commands.command()
    async def clear(self, ctx):
        await ctx.send('Очередь воспроизведения очищена')
        tracks_queue.clear()

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
