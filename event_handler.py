import re
import os
import pymongo

# create a response to a user submitting a score
def saveScoreEvent( message ):
    messageContent = message.content
    messageAuthor = message.author
    day = getDayFromMessage( messageContent )
    # Check if a user has already submitted a score for this day
    froggieDB = getMongoDBClient()
    attempts = froggieDB['Attempts']
    attemptExists = attempts.find_one( {'discordUserID': messageAuthor.id, 'day': day} )
    if ( day == -1 ):
        return 'Invalid day in your attempt'
    if ( attemptExists ):
        return 'You have already submitted a score for this day'
    score = getScoreFromMessage( messageContent )
    if ( score == -1 ):
        return 'Invalid score in your attempt'
    
    froggieDB = getMongoDBClient()
    attempts = froggieDB['Attempts']
    users = froggieDB['Users']
    userExists = users.find_one( {'_id': messageAuthor.display_name} )
    # if this is a new user, make a record of them in the 'Users' collection in MongoDB
    if ( not userExists ):
        userEntry = { '_id': messageAuthor.display_name, 'discordUserID': messageAuthor.id }
        users.insert_one( userEntry )
        print( 'new user added to DB' )

    entry = { 'discordUserID': messageAuthor.id, 'nickname': messageAuthor.display_name, 'day': day, 'score': score }
    attempts.insert_one( entry )
    return getPlayerStatsString( attempts, messageAuthor.id, messageAuthor.display_name )

# create a response to a user requesting the stats of a player
def requestPlayerStatsEvent( message ):
    froggieDB = getMongoDBClient()
    users = froggieDB['Users']
    attempts = froggieDB['Attempts']

    requestedUser = getUserFromStatRequestMessage( message )
    requestedUserEntry = users.find_one( {'_id': requestedUser} )
    if ( not requestedUserEntry ):
        return f'could not find user with name of {requestedUser}'
    requestedUserID = requestedUserEntry['discordUserID']
    return getPlayerStatsString( attempts, requestedUserID, requestedUser )

# create a response to a user requesting a leaderboard
def leaderboardEvent( message, client ):
    froggieDB = getMongoDBClient()
    leaderboard = {}
    users = froggieDB['Users']
    attempts = froggieDB['Attempts']
    userCursor = users.find()
    # iterate over all users and record their scores in the leaderboard dict
    for user in userCursor:
        discordUserID = int( user['discordUserID'] )
        discordUserName = client.get_user( discordUserID ).display_name
        userPoints = 0
        for i in range ( 1, 8 ):
            if ( not i == 7 ):
                attemptCount = attempts.count_documents( {'discordUserID': discordUserID, 'score': i} )
                userPoints = userPoints + ( attemptCount * ( 8 - i ) )
            else:
                attemptCount = attempts.count_documents( {'discordUserID': discordUserID, 'score': i-7} )
                userPoints = userPoints + attemptCount
        leaderboard[discordUserName] = userPoints
    # sort the dictionary according to score
    sortedLeaderboard = dict( reversed( sorted( leaderboard.items(), key=lambda item: item[1] ) ) )
    # build the leaderboard string
    returnMsg = 'Username                | Score\n'
    returnMsg = returnMsg + '--------------------------------\n'
    for user in sortedLeaderboard:
        userRecord = user
        if ( len( user ) < 24 ):
            for i in range( 0, 24 - len( user ) ):
                userRecord = userRecord + ' '
        userRecord = userRecord + f'| {sortedLeaderboard.get( user )}\n'
        returnMsg = returnMsg + userRecord
    return returnMsg

# delete all the collections in the MongoDB FroggieDB
def deleteAllCollectionsEvent():
    froggieDB = getMongoDBClient()
    users = froggieDB['Users']
    attempts = froggieDB['Attempts']
    userDeletions = users.delete_many( {} )
    attemptsDeletions = attempts.delete_many( {} )
    return f'deleted {userDeletions.deleted_count} users and {attemptsDeletions.deleted_count} attempts'

# return a string which displays the users stats
def getPlayerStatsString( attempts, discordUserID, discordUserDisplayName ):
    userPoints = 0
    numAttempts = attempts.count_documents( {'discordUserID': discordUserID} )
    scoreString = ''
    for i in range( 1, 8 ):
        if ( not i == 7 ):
            attemptCount = attempts.count_documents( {'discordUserID': discordUserID, 'score': i} )
            scoreString = scoreString + f'\t> {i}/6 attempts: {attemptCount}\n'
            userPoints = userPoints + ( attemptCount * ( 8 - i ) )
        else:
            attemptCount = attempts.count_documents( {'discordUserID': discordUserID, 'score': i-7} )
            scoreString = scoreString + f'\t> X/6 attempts: {attemptCount}'
            userPoints = userPoints + attemptCount
    return f'{discordUserDisplayName} has {numAttempts} total attempts with {userPoints} points. Average score is {round((userPoints/numAttempts), 2)}.\n{scoreString}.'

# open a new MongoDB client to store and request data
def getMongoDBClient():
    froggieDBPassword = os.environ.get( 'ROBO_FROGGIE_DB_PASSWORD' )
    dbclient = pymongo.MongoClient( f'{froggieDBPassword}')
    print( 'connected to MongoDB successfully' )
    return dbclient['FroggieDB']

# use regex to get the day (3-4 digit number) from the message
def getDayFromMessage( messageContent ):
    dayGroup = re.search( r'(\s[0-9]{3}\s)|(\s[0-9]{4}\s)', messageContent )
    if (not dayGroup):
        return -1
    day = int( dayGroup.group().strip() )
    return day

# use regex to get the score (digits 1-6 or X for failure) from the message
def getScoreFromMessage( messageContent ):
    scoreGroup = re.search( r'\s([1-6]|X)/6', messageContent )
    if (not scoreGroup):
        return -1
    scoreStr = scoreGroup.group().strip()[0]
    if ( scoreStr == 'X' ):
        scoreStr = '0'
    score = int( scoreStr )
    return score

# get the name of the user from a stat request message
def getUserFromStatRequestMessage( message ):
    messageContent = message.content
    whitespaceIndex = messageContent.find( " " )
    requestedUser = messageContent[whitespaceIndex + 1 : ]
    return requestedUser