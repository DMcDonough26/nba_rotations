import pandas as pd
from nba_api.stats.endpoints import gamerotation, teamgamelog
import plotly.express as px
import pandas as pd
from nba_api.stats.static import teams
import time
import math
from datetime import datetime


# provide the team name, year, portion of season, and receive the game logs for those games
def get_game_logs(team='Knicks',season='2022-23',season_mode='Playoffs',start='1900-1-1',end='2100-1-1'):
    team_id = teams.find_teams_by_full_name(team)[0]['id']
    game_log_df = teamgamelog.TeamGameLog(season=season,season_type_all_star=season_mode,team_id=team_id).get_data_frames()[0]
    game_log_df['GAME_DATE'] = pd.to_datetime(game_log_df['GAME_DATE'])
    sy, sm, sd = start.split('-')
    ey, em, ed = end.split('-')
    game_log_df['keep_ind'] = game_log_df['GAME_DATE'].apply(lambda x: 1 if ((x >= datetime(int(sy),int(sm),int(sd)))&\
                                                   (x <= datetime(int(ey),int(em),int(ed)))) else 0)
    game_log_df['home_ind'] = (game_log_df['MATCHUP'].apply(lambda x: len(x.split('@')))-2)*-1

    return game_log_df[game_log_df['keep_ind']==1]

# provide game logs for game IDs and receive the full rotation data for each game
def get_rotation_data(game_log_df):

    # call NBA API for rotation data
    for i in range(len(game_log_df)):

        # grab correct frame based on whether user-input team was home or away
        if game_log_df.iloc[i]['home_ind'] == 0:
            temp_df = gamerotation.GameRotation(game_id=game_log_df.iloc[i]['Game_ID'],league_id='00').get_data_frames()[0]
            temp_df['GAME_DATE'] = game_log_df.iloc[i]['GAME_DATE']
        else:
            temp_df = gamerotation.GameRotation(game_id=game_log_df.iloc[i]['Game_ID'],league_id='00').get_data_frames()[1]
            temp_df['GAME_DATE'] = game_log_df.iloc[i]['GAME_DATE']

        # build the dataframe
        if i == 0:
            full_df = temp_df.copy()
        else:
            full_df = pd.concat([full_df,temp_df],axis=0)
        time.sleep(1)

    full_df['Name'] = full_df['PLAYER_FIRST']+' '+full_df['PLAYER_LAST']
    return full_df

# create indicator for which minutes the player played in a game
def updatefunc(x, time_in, time_out):
    if ((x['Minute'] >= time_in)&(x['Minute'] <= time_out)):
        return min(x['On']+1,1)
    else:
        return x['On']

# cycle through runs by player by game to create a dataframe showing all 48 minutes by player by game
def process_rotations(full_rotation_data):

    k = 0
    for game in full_rotation_data['GAME_ID'].unique():
        game_df = full_rotation_data[full_rotation_data['GAME_ID']==game].copy()

        i = 0
        for player in game_df['Name'].unique():
            min_list = range(48)
            name_list = [player] * 48
            on_ind = [0] * 48
            temp_df = pd.DataFrame({'Minute':min_list,'Name':name_list,'On':on_ind})

            player_df = game_df[game_df['Name']==player].copy()

            for j in range(len(player_df)):
                time_in = math.floor(player_df.iloc[j]['IN_TIME_REAL']/600)
                time_out = math.ceil(player_df.iloc[j]['OUT_TIME_REAL']/600)
                temp_df['On'] = temp_df.apply(updatefunc, axis=1, args=(time_in,time_out))

            if ((i == 0)&(k == 0)):
                running_df = temp_df.copy()
            else:
                running_df = pd.concat([running_df,temp_df],axis=0)

            i += 1
        k += 1

    return running_df

# establish when a run started
def start(x):
    if ((x['Minute'] == 0)&(x['On'] == 1)):
        return 1
    elif x['diff'] == 1:
        return 1
    else:
        return 0

# establish when a run ended
def end(x):
    if ((x['Minute'] == 47)&(x['On'] == 1)):
        return 1
    elif ((x['diff'] == -1)&(x['On'] == 0)&(x['Minute'] == 0)):
        return 0
    elif x['diff'] == -1:
        return 1
    else:
        return 0

# return a dataframe showing the averge subsitution patters of each player
def get_player_averages(full_player_data, game_log_df, freq=0.5):

    # aggregate data
    output_df = full_player_data.groupby(['Name','Minute'])['On'].sum().reset_index()
    output_df['On'] = output_df['On']/len(game_log_df)
    output_df['On'] = output_df['On'].apply(lambda x: 1 if x >= freq else 0)

    # establish runs for the aggregated data
    output_df['diff'] = output_df['On'].diff()
    output_df['start'] = output_df.apply(start,axis=1)
    output_df['end'] = output_df.apply(end,axis=1)

    # create a final dataframe for plotting
    final_df = pd.concat([output_df[output_df['start']==1][['Name','Minute']].reset_index(drop=True),output_df[output_df['end']==1][['Minute']].\
                             reset_index(drop=True)],axis=1)
    final_df.columns = ['Name','Start','End']
    final_df['Delta'] = final_df['End'] - final_df['Start']

    return final_df

# plot the averages
def plot_averages(average_player_data):
    fig = px.timeline(average_player_data, x_start="Start", x_end="End", y="Name", color="Name")
    fig.layout.xaxis.type = 'linear'
    for d in fig.data:
        filt = average_player_data['Name'] == d.name
        d.x = average_player_data[filt]['Delta'].tolist()
    fig.show()
