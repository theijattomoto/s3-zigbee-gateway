#! /usr/bin/python3

# Script properties for internal functions
cycletime = 1400										    	# Node polling cycle time
pollinggap = 3											    	# Polling interval between nodes
			# (num of nodes) * (pollinggap) = (minimum cycle time)
active_time = '19:30'										    # Lantern ON reference time
GPS_poll_time = '01:00'										    # GPS Mapping start reference time
inactive_time = '06:46'										    # Lantern OFF reference time
LM_active_time = '19:00'									    # Manual overriding reference ON time
node_off_time = '07:00'										    # Manual overriding reference OFF time
aggressive_poll_duration_mins = 90								# Aggressive polling duration for nodes starting from active_time
minimum_power = 15.0										    # Power check for lantern if Lantern is OFF during active hours 
max_msgID_count = 250                                           # Max MsgID implemented

# HTTP/MQTT-related variables
test_align_flag = False
cert_codename = 'dbkl'
topic_header = 'nodes/data/'                                    # MQTT topic header
client_ID = 'INSERTTOPIC1HERE'                                  # client ID for first instance
client_ID_2 = 'INSERTTOPIC2HERE'								# client ID for second instance (normally not used unless dual-polling required, run PYGatewayListener_v1.0_2)

# Static gateway and database specs
localDBpath = 'INSERTCSVNAMEHERE.csv'			    		    # Local deploy node list file in RaspPi
first_GW_data = ('FE01', '1001', '20')                          # First gateway node specifications
second_GW_data = ('FE02', '1001', '20')                         # Second gateway node specifications

# Auto-generated files repositories
problemlogpath = 'errorlog'
logfilepath = 'log'                                 		    # Local log repository
maplogpath = 'GPSlog'					    		    		# Daily map repository
GPS_style1 = ['downArrowIcon', 'http://maps.google.com/mapfiles/kml/pal4/icon28.png']       	    # Represents '#G0!' on map 
GPS_style2 = ['whiteBlankIcon', 'http://maps.google.com/mapfiles/kml/paddle/wht-blank.png'] 	    # Represents '#G0-' on map
GPS_style3 = ['redStarIcon', 'http://maps.google.com/mapfiles/kml/paddle/red-stars.png']    	    # Represents '#G0|V|' and '#G0|V|NoFix' on map

# Packet structures
msgID = 'XXXXX'											    	# Message ID length
msgID_vers = 1                                                  # Max version implemented on msgID
nodeID = 'XXXX'                                                 # Node ID length