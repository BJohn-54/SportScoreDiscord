# -*- coding: utf-8 -*-

import asyncio
from discord.ext import commands, tasks
import discord
import httpx
from bs4 import BeautifulSoup
from cogs.utils import FLAGS_DATA
import emoji
from config import *
import hashlib
from logs import log_exception_traceback


class cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CATEGORIES = {}
        self.matches = {}
        self.dms = {}
        self.TEAMS = {}
        self.NOTIFICATIONS = {}
        self.keep_it_running.start()
    
    def get_team_id(self, text):
        text_bytes = text.encode('utf-8')
        sha256_hash = hashlib.sha256(text_bytes)
        unique_id = int.from_bytes(sha256_hash.digest()[:8], byteorder='big')
        return unique_id

    async def parse_team_data(self, link, match_id, match_score, team_1, team_2, score, league_name):
        try:
            async with httpx.AsyncClient() as client:
                url = f'https://sportscore.io{link}'
                r = await client.get(url=url, timeout=10000)
                s = BeautifulSoup(r.content, 'html.parser')
                stats = s.find_all(class_='col-1 px-0')
                time = s.find('div', {'id': 'up-score-separator'})
                timetext = f':alarm_clock: Time (Minutes): {time.text}\n\n' if time is not None else ''
                STATS_DATA = []
                for stat in stats[:6]:
                    STATS_DATA.append(stat.text)
                self.matches[match_id] = {
                    'team': match_score,
                    'data': STATS_DATA,
                    'time': timetext,
                    'category': league_name,
                    'url': url
                }
                if match_id in self.NOTIFICATIONS:
                    old = self.NOTIFICATIONS[match_id]['data']
                    old_score = self.NOTIFICATIONS[match_id]['score']
                    if (old != STATS_DATA) or (score != old_score) or ('90' in timetext):
                        self.NOTIFICATIONS[match_id]['data'] = STATS_DATA
                        self.NOTIFICATIONS[match_id]['score'] = score
                        embed, components = await self.get_team_data(match_id, STATS_DATA, match_score, timetext, league_name, url)
                        content = None
                        if score != old_score:
                            old = old_score.split(' - ')
                            new = score.split(' - ')
                            if old[0] != new[0]:
                                content = f'**{team_1}** scored against **{team_2}**!'
                            else:
                                content = f'**{team_2}** scored against **{team_1}**!'
                        else:
                            if old[0] != STATS_DATA[0]:
                                content = f'**{team_1}** got a **Corner Kick**!'
                            elif old[1] != STATS_DATA[1]:
                                content = f'**{team_1}** got a **Red Card**!'
                            elif old[2] != STATS_DATA[2]:
                                content = f'**{team_1}** got a **Yellow Card**!'
                            elif old[3] != STATS_DATA[3]:
                                content = f'**{team_2}** got a **Yellow Card**!'
                            elif old[4] != STATS_DATA[4]:
                                content = f'**{team_2}** got a **Red Card**!'
                            elif old[5] != STATS_DATA[5]:
                                content = f'**{team_2}** got a **Corner Kick**!'
                            elif '90' in timetext:
                                if '90' not in self.NOTIFICATIONS[match_id]['time']:
                                    content = f'Match has been ended!'

                        if content:
                            embed.description = f'{content}\n\n{embed.description}'
                            components = [[
                                discord.Button(label='Dismiss', custom_id='dismiss'),
                                discord.Button(label='Unnotify', custom_id=f'unnotify|{match_id}')
                            ]]  
                            self.dms[embed] = {
                                'user': self.NOTIFICATIONS[match_id]['user'],
                                'comp': components
                            }
        except Exception as e:
            log_exception_traceback(e)

    @tasks.loop(minutes=1)
    async def keep_it_running(self):
        if not self.update_categoies_data.is_running():
            self.update_categoies_data.start()

    @tasks.loop(seconds=20)
    async def update_categoies_data(self):
        try:
            options = {}
            self.matches = {}
            self.dms = {}
            semaphore = asyncio.Semaphore(10)
            tasks = []
            async with httpx.AsyncClient() as client:
                    for i in [1, 2, 3]:
                        response = await client.get(f'https://sportscore.io/?page={i}', timeout=10000)
                        soup = BeautifulSoup(response.content, 'html.parser')
                        tr_elements = soup.find_all('tr')
                        for tr in tr_elements:
                            try:
                                td_elements = tr.find_all('td')
                                desc = td_elements[0].find('a')
                                if desc:
                                    link = desc.get('href')
                                    if len(td_elements) > 5:
                                        team_1 = td_elements[2].text.strip()
                                        score = td_elements[3].text.strip()
                                        team_2 = td_elements[4].text.strip()
                                        match_id = self.get_team_id(f'{team_1} {team_2}')
                                        match_score = f'{team_1} | {score} | {team_2}'
                                        options[league_name]['teams'][match_score] = match_id
                                        tasks.append(self.parse_team_data(link, match_id, match_score, team_1, team_2, score, league_name))
                                else:
                                    category = tr

                                    if flag := category.find('img'):
                                        flag = flag['alt'].replace('flag', '').strip()
                                    else:
                                        flag = ''
                                    
                                    try:
                                        league_name = category.find('b').text
                                    except:
                                        self.CATEGORIES = {}
                                        self.TEAMS = {}
                                        return
                                    
                                    if flag in FLAGS_DATA:
                                        flag = FLAGS_DATA[flag]

                                    options[league_name] = {
                                        'teams': {},
                                        'flag': flag if emoji.is_emoji(flag) else '🗺️' if 'international' in league_name.lower() else '⚽'
                                    }
                            except Exception as e:
                                print(e)
            async with semaphore:
                await asyncio.gather(*tasks)
            self.CATEGORIES = options
            self.TEAMS = self.matches
                
            self.NOTIFICATIONS = {match: value for match, value in self.NOTIFICATIONS.items() if match in self.TEAMS}

            if self.dms:
                for embed in self.dms:
                    try:
                        await self.dms[embed]['user'].send(embed=embed, components=self.dms[embed]['comp'])
                        await asyncio.sleep(1)
                    except Exception as e:
                        print(e)
        except Exception as e:
            log_exception_traceback(e)

    @update_categoies_data.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()

    async def go_to_categories(self, interaction):
        DICT = self.CATEGORIES.copy()
        options = [category for category in DICT]
        if len(options) != 0:
            menus = []        
            select_options = [discord.SelectOption(label=option, value=option, emoji=DICT[option]['flag']) for option in options]
            batches = [select_options[i:i+25] for i in range(0, len(select_options), 25)]
            for op in batches:
                menus.append(discord.SelectMenu(custom_id='category', options=op, placeholder='Select a Category', min_values=1, max_values=1))
            await interaction.edit(components=[menus])
        else:
            embed = discord.Embed(color=COLOR)
            embed.description = f'Matches not found atm! Please try again later!'
            await interaction.respond(embed=embed, hidden=True)

    async def go_to_matches(self, interaction, category):
        if category in self.CATEGORIES:
            DICT = self.CATEGORIES.copy()
            menus = []
            options = [match for match in DICT[category]['teams']]
            select_options = [discord.SelectOption(label=option, value=str(DICT[category]['teams'][option])) for option in options]
            batches = [select_options[i:i+25] for i in range(0, len(select_options), 25)]
            for op in batches:
                menus.append(discord.SelectMenu(custom_id=f'match', options=op, placeholder='Select a Match', min_values=1, max_values=1))
            menus.append(discord.Button(label='Back', custom_id='categories'))
            await interaction.edit(components=[menus], embed=None)
        else:
            await self.go_to_categories(interaction)

    @commands.Cog.listener()
    async def on_selection_select(self, interaction: discord.ComponentInteraction, select_menu: discord.SelectMenu):
        try:
            if select_menu.custom_id == 'category':
                await interaction.defer()
                await self.go_to_matches(interaction, select_menu.values[0])
            elif select_menu.custom_id.startswith('match'):
                await interaction.defer()
                embed, components = await self.get_team_data(select_menu.values[0])
                await interaction.edit(embed=embed, components=components)
        except Exception as e:
            log_exception_traceback(e)
        
    @commands.Cog.listener()
    async def on_raw_button_click(self, interaction: discord.ApplicationCommandInteraction, button: discord.Button):
        try:
            if button.custom_id.startswith('refresh'):
                await interaction.defer()
                embed, components = await self.get_team_data(button.custom_id.split('|||')[-1])
                if 'match has been ended' in embed.description:
                    await interaction.respond(embed=embed, hidden=True)
                else:
                    await interaction.edit(embed=embed, components=components)
            elif button.custom_id.startswith('notify'):
                await interaction.defer()
                id = int(button.custom_id.split('|||')[-1])
                embed = discord.Embed(color=COLOR)
                try:
                    data = self.TEAMS[id]['data']
                    teams = self.TEAMS[id]['team'].split(' | ')
                except:
                    embed.description = f'This match has been ended!'
                    await interaction.respond(embed=embed, hidden=True)
                else:
                    team_id = self.get_team_id(f'{teams[0]} {teams[-1]}')
                    self.NOTIFICATIONS[team_id] = {
                        'user': interaction.author,
                        'data': data,
                        'score': teams[1]
                    }
                    embed.description = f'Notifications were successfully enabled!'
                    await interaction.respond(embed=embed, hidden=True)
            elif button.custom_id == 'categories':
                await interaction.defer()
                await self.go_to_categories(interaction)
            elif button.custom_id == 'dismiss':
                await interaction.message.delete()
            elif button.custom_id.startswith('unnotify'):
                await interaction.defer()
                try:
                    id = int(button.custom_id.split('|')[-1])
                    if id in self.NOTIFICATIONS:
                        self.NOTIFICATIONS.pop(id)
                except Exception as e:
                    print(e)
                await interaction.message.delete()
            elif button.custom_id.startswith('matches'):
                await interaction.defer()
                category = button.custom_id.split('|||')[-1]
                await self.go_to_matches(interaction, category)                   
        except Exception as e:
            log_exception_traceback(e)

    async def get_team_data(self, id, data=None, teams=None, time=None, category=None, url=None):
        try:
            if data == None:
                data = self.TEAMS[int(id)]['data']
                teams = self.TEAMS[int(id)]['team']
                time = self.TEAMS[int(id)]['time']
                category = self.TEAMS[int(id)]['category']
                url = self.TEAMS[int(id)]['url']
        except:
            embed = discord.Embed(color=COLOR)
            embed.description = 'This match has been ended!'
            components = []
        else:
            embed = discord.Embed(color=COLOR)
            embed.title = teams
            teams = teams.split(' | ')
            if len(data) > 5:
                embed.description = f'{time}**🏆 {teams[0]}**\n`- `Corner Kick: {data[0]}\n`- `Red Card: {data[1]}\n`- `Yellow Card: {data[2]}\n\n**🏆 {teams[-1]}**\n`- `Corner Kick: {data[5]}\n`- `Red Card: {data[4]}\n`- `Yellow Card: {data[3]}'
            else:
                embed.description = 'Data is being loaded. Please click refresh!'
            embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar_url)
            components = [[
                discord.Button(label='Notify', custom_id=f'notify|||{id}'),
                discord.Button(label='Refresh', custom_id=f'refresh|||{id}'),
                discord.Button(label='Back', custom_id=f'matches|||{category}'),
                discord.Button(label='Live', url=url),
            ]]
        return embed, components

    @commands.Cog.slash_command(base_name='matches', base_desc='Match Commands', name='all', description='All Matches from https://sportscore.io/')
    async def score(self, interaction: discord.ApplicationCommandInteraction):
        try:
            await interaction.defer(hidden=True)
            DICT = self.CATEGORIES.copy()
            options = [category for category in DICT]
            if len(options) != 0:
                menus = []        
                select_options = [discord.SelectOption(label=option, value=option, emoji=DICT[option]['flag']) for option in options]
                batches = [select_options[i:i+25] for i in range(0, len(select_options), 25)]
                for op in batches:
                    menus.append(discord.SelectMenu(custom_id='category', options=op, placeholder='Select a Category', min_values=1, max_values=1))
                await interaction.respond(components=[menus])
            else:
                embed = discord.Embed(color=COLOR)
                embed.description = f'Matches not found atm! Please try again later!'
                await interaction.respond(embed=embed)
        except Exception as e:
            log_exception_traceback(e)
    
    @commands.Cog.slash_command(base_name='matches', base_desc='Match Commands', name='search', description='Search Matches from https://sportscore.io/', options=[
        discord.SlashCommandOption(
            name='team',
            description='Search match by name!',
            option_type=str,
            required=True,
            autocomplete=True
        )
    ])
    async def search(self, interaction: discord.ApplicationCommandInteraction, team: str):
        try:
            await interaction.defer(hidden=True)
            teams = team.split(' | ')
            team_id = self.get_team_id(f'{teams[0]} {teams[-1]}')
            if team_id in self.TEAMS:
                embed, components = await self.get_team_data(team_id)
                await interaction.respond(embed=embed, components=components)
            else:
                embed = discord.Embed(color=COLOR)
                embed.description = 'This match has been ended!'
                await interaction.respond(embed=embed)
        except Exception as e:
            log_exception_traceback(e)
    
    @search.autocomplete_callback
    async def auto_for_search(self, i: discord.AutocompleteInteraction, team: str = ''):
        try:
            if team and team.focused:
                DICT = self.CATEGORIES.copy()
                options = []
                for c in DICT:
                    options.extend(DICT[c]['teams'])
                query_lower = team.lower()
                filtered_elements = filter(lambda x: query_lower in x.lower(), options)
                choices = [discord.SlashCommandOptionChoice(name=word, value=word) for word in list(filtered_elements)[:25]]                    
                await i.send_choices(choices)
        except Exception as e:
            log_exception_traceback(e)


def setup(bot):
    bot.add_cog(cog(bot))