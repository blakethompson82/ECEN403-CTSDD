# The following is used for controlling a Hexacopter using a
# Raspberry Pi 3 Model B (RP3) and a Pixhawk 2.4.8, using Dronekit(Mavlink)
# Flight path script for mulit-altitude flight paths




# Import Dronekit-Python
from dronekit import connect, VehicleMode, time, LocationGlobal
import math
import scipy.integrate as integrate
import measurements as data


##############################################################################

# Function that returns the next point to fly to
def Next_Point(distance, angle, lat1, long1, altitude):

    lat2 = (lat1 * math.pi) / 180               # Converts latitude angle to radians
    long2 = (long1 * math.pi) / 180             # Converts longitude angle to radians


    lower_lat = math.floor(lat1)     # Finds the latitude line above the current location
    upper_lat = math.ceil(lat1)      # Finds the latitude line below the current location

    polar_lower_lat = (lower_lat * math.pi) / 180   # Converts lower_lat to radians since trig functions in 'math' use radians
    polar_upper_lat = (upper_lat * math.pi) / 180   # Converts upper_lat to radians since trig functions in 'math' use radians

    lower_angle = (math.atan((6378137.0/6356752.0) * math.tan(polar_lower_lat)))    # Angle (polar) between equator and upper latitude line
    upper_angle = (math.atan((6378137.0/6356752.0) * math.tan(polar_upper_lat)))    # Angle (polar) between equator and upper latitude line
                                                                                    # 6356752.0 = Polar radius of Earth      (meters)
                                                                                    # 6378137.0 = Equitorial radius of Earth (meters)


    def integrand(x):
        return math.sqrt(((6378137**2) * ((math.sin(x))**2)) + ((6356752**2) * ((math.cos(x))**2)))

    lat_difference1 = integrate.quad(integrand, lower_angle, upper_angle)           # Integral to find the arc length between latitiude lines of the earth (meters)

    lat_difference2 = lat_difference1[0]    # integrate.quad outputs  a tuple with two items in the list, this extracts the first and leaves the error

    angle_rad = (angle * math.pi) / 180     # Direction that drone will be traveling, given in terms of the unit circle (radians)

    arc_length_per_degree = 111317.4306     # Arc length per degree of longitude at Earth's equator (meters)

    long_difference = math.cos(lat2) * arc_length_per_degree  # Calculates length between each degree of longitude, based on latitude coordinate


    dx = distance * math.cos(angle_rad)     # Change in x direction (meters)
    dy = distance * math.sin(angle_rad)     # Change in y direction (meters)

    delta_longitude = dx / long_difference  # Converts change in x to change in longitude   (meters)

    delta_latitude = dy / lat_difference2   # Converts change in y to change in latitude    (meters)

    long3 = long1 + delta_longitude         # Adds change in longitude to original longitude to give new longitude point
    lat3 = lat1 + delta_latitude            # Adds change in latitude to original latitude to give new latitude point


    return [lat3,long3,altitude]
######################################################################################################
# Converts compass heading to comparable unit circle degree, since the Next_point function uses an input of unit circle degrees
def Heading_to_unit_circle(heading_degree):
                                                    # Compass heading increases with rotation in the clockwise direction
                                                    # Unit circle angle increases with rotation in counter-clockwise direction

    if 90 < heading_degree <= 360:                       # Checks to make sure that the input angle does not exceed 360 and instead starts back over at 0
        unit_circle_degree = (360 - heading_degree) + 90
    elif 0 <= heading_degree <= 90:
        unit_circle_degree = 90 - heading_degree

    return unit_circle_degree



#####################################################################################################################
# Function used to calculate GPS coordinates for drone to fly to

def GPS_Coords(far_field, heading, lat_ant, long_ant, alt_list, points_per_path, number_paths):
    total_points = points_per_path * number_paths


    if heading > 120 and heading <=240:
    	degree_left = heading - 120 			# heading for far left of pattern (starting facing the antenna)
    	degree_right = heading + 120			# heading for far right of pattern (starting facing the antenna)
    elif heading < 120:							# vehicle.heading has a range of 0-360
    	degree_left = 360 - (120 - heading)
    	degree_right = heading + 120
    elif heading > 240:
    	degree_left = heading - 120
    	degree_right = (heading + 120) - 360


    new_degree_left = Heading_to_unit_circle(degree_left)       # Converts left most degree of travel to unit circle angle
    new_degree_right = Heading_to_unit_circle(degree_right)     # Converts right most degree of travel to unit circle angle


    degree = 120 / (points_per_path - 1)            # Angle between each point, referenced from antenna (degrees)
    degree_polar = (degree  * math.pi)  / 180     # Angle between each point, referenced from antenna (polar)


    z = 0								            # Variable for incrementing in teh following for loop
    point_list_arc1 = [0] * total_points			# Creates a list with number of entries equal to the number of desired points for the drone to travel to
    #print(new_degree_left)
    #print(new_degree_right)

    for z in range(0,total_points,1):                               # A for loop that goes through each point to assign a GPS location to it
        if ((z/points_per_path) % 2) == 0:                          # Checks for even number paths (path starts on left)
            i = ((z % points_per_path) * degree) + new_degree_left
            if i >= 360:                                            # Ensures that angle wraps back around if angle is greater than 360
                next_angle = i - 360
            else:
                next_angle = i

            #print(next_angle)
            point_list_arc1[z] = Next_Point(far_field, next_angle, lat_ant, long_ant,alt_list[z / points_per_path])     # Fills in list with desired number of GPS coordinates


        if ((z/points_per_path) % 2) == 1:                          # Checks for even number paths (path starts on right)
            i = new_degree_right - ((z % points_per_path) * degree)
            if i < 0:                                               # Ensures that angle wraps back around if angle is less than 0
                next_angle = (360 + i)
            else:
                next_angle = i
            #print(next_angle)


            point_list_arc1[z] = Next_Point(far_field, next_angle, lat_ant, long_ant,alt_list[z / points_per_path])     # Fills in list with desired number of GPS coordinates



    return (point_list_arc1)     # Output list of GPS coordinates to terminal



########################################################################################################
# User input values
file_path = data.filePath()
antenna_frequency = raw_input("Antenna Frequency (Must be positive integer): ")        # MUST be an odd number, to satisfy 'range' used in GPS_Coords function


while not (antenna_frequency.isdigit()):                                #checks that input is an integer
    print("Input is not a positive integer")
    print(" ")
    antenna_frequency = raw_input("Antenna Frequency (Must be positive integer): ")

antenna_frequency = float(antenna_frequency)                        #Converts frequency to float for later calculations

antenna_length = input("Antenna Length (Must be positive integer): ")        # MUST be an odd number, to satisfy 'range' used in GPS_Coords function




antenna_length = float(antenna_length)                          #Converts antenna length to float for later calculations

wavelength = float(( 3 * (10 ** 8)) / antenna_frequency)

far_field = float((2 * (antenna_length ** 2)) / wavelength) # Far field calculation for antenna

points_per_path = raw_input("Number of points (MUST be odd number): ")        # MUST be an odd number, to satisfy 'range' used in GPS_Coords function

while not (points_per_path.isdigit()):                                #checks that input is an integer
    print("Input is not a positive integer")
    print(" ")
    points_per_path = raw_input("Number of points? (MUST be odd number of 3 or more): ")

points_per_path = int(points_per_path)
while ((points_per_path < 2) | (points_per_path % 2 == 0)):                                            #Checks that an odd number of 3 points is input
    print("Input odd number of at least 3")
    points_per_path =  input("Number of points? (MUST be odd number of 3 or more): ")
points_per_path = int(points_per_path)

number_paths = raw_input("Number of paths? (Must be positive integer): ")
while not (number_paths.isdigit()):                                #checks that input is an integer
    print("Input is not a positive integer")
    print(" ")
    number_paths = raw_input("Number of points? (MUST be odd number of 3 or more): ")

number_paths = int(number_paths)
total_points = points_per_path * number_paths
########################################################################################################
# Connect to the vehicle, perform checks, and give control of drone to user
print("Connecting to a vehicle on: /dev/ttyS0")
vehicle = connect('/dev/ttyS0',wait_ready = True, baud = 921600)	#Checks to see if the drone has booted, has GPS fix, and
																		#comleted pre-arm



#while not vehicle.is_armable:
#	print "Waiting for vehicle to initialize..."
#	time.sleep(1)



while not vehicle.channels['5'] >= 1200:
	print("Turn on manual mode(Flight Mode Switch = 1): Current Flight Mode Switch = 0")
	time.sleep(1)

# Flight Mode Switch position 2 = Guided Mode
# Flight Mode Switch position 1 = Manual Mode
# Flight Mode Switch position 0 = Manual Mode and capture GPS location of antenna

print("Mode: %s") %vehicle.mode.name

while not vehicle.armed:				#waits for vehicle to be armed
	vehicle.armed = True
	time.sleep(1)


print("Armed: %s") %vehicle.armed
time.sleep(2)



vehicle.mode = VehicleMode("STABILIZE")		#enables user control
vehicle.flush()

print("Stabilize")

############################################################################################
# Manual flight and calculate GPS coordinates for flight path

while vehicle.channels['5'] >= 1200:		#if Flight Mode = 0 or 1 on controller, it is in manual flight

	# A switch on the remote will be used to toggle drone being controlled
	# by the user or the Raspberry Pi
    print("Manual flight")

    while vehicle.channels['5'] > 1600:		#if Flight Mode = 0 on controller, it is gathering antenna coordinates
	lat_ant = vehicle.location.global_frame.lat	#sets antenna latitude
	long_ant = vehicle.location.global_frame.lon	#sets antenna londitude
	alt_ant = vehicle.location.global_frame.alt	#sets antenna altitude
	heading = vehicle.heading					#sets compass heading of drone at antenna
        print("Gathering data")
        time.sleep(1)
    time.sleep(1)
alt_list = [0] * number_paths                       # Creates list of altitudes for each flight path
for i in range(0,len(alt_list),1):               # Drops each consecutive flight path by 1 meter from start altitude of the antenna altitude
    alt_list[i] = alt_ant - (i * 2) 

print(lat_ant)
print(long_ant)
print(alt_ant)
print(heading)

if heading > 120 and heading <=240:
	degree_left = heading - 120 			# heading for far left of pattern (starting facing the antenna)
	degree_right = heading + 120			# heading for far right of pattern (starting facing the antenna)
elif heading < 120:							# vehicle.heading has a range of 0-360
	degree_left = 360 - (120 - heading)
	degree_right = heading + 120
elif heading > 240:
	degree_left = heading - 120
	degree_right = (heading + 120) - 360


new_degree_left = Heading_to_unit_circle(degree_left)       # Converts left most degree of travel from compass heading to unit circle angle
new_degree_right = Heading_to_unit_circle(degree_right)     # Converts right most degree of travel from compass heading to unit circle angle


GPS_Coord_List = GPS_Coords(far_field, heading, lat_ant, long_ant, alt_list, points_per_path, number_paths) # Uses GPS_Coords function to calculate all points to fly to

print(GPS_Coord_List)

print("Got Coordinates")

velocity = float(1)							# Determines how fast the drone will fly
time_wait_1 = (far_field / velocity) + 0.5		# Calculates time (seconds) before next command is issued so drone can get to next location
#point_1 = GPS_Coord_List[0]                     # Extractst the first point from the list of GPS coordinates
#lat1 = point_1[0]                               # Extracts the latidude of the first coordinate
#long1 = point_1[1]                              # Extracts the latidude of the first coordinate
#alt1 = point_1[2]                               # Extracts the altitude of the first coordinate
################################################################################################
# Autonomous Flight

vehicle.mode = VehicleMode("GUIDED")
vehicle.flush()

while not vehicle.mode.name=='GUIDED':              # Checks to make sure vehicle is in GUIDED moded
    print("Vehicle not in GUIDED mode")
    vehicle.mode = VehicleMode("GUIDED")
    vehicle.flush()
    time.sleep(1)

print("Should be in GUIDED mode")
print(vehicle.mode.name)


while vehicle.channels['5'] < 1200:		# If Flight Mode = 2 on controller, it is in autonomous mode

    if vehicle.channels['5'] >=  1200:
        break

	#vehicle.simple_goto(LocationGlobal(lat1, long1, alt1), groundspeed = 1)	# Commands the drone to go the the desired location at 0.5 m/s

    for t in range(1,int(math.ceil(time_wait_1)) * 2, 1):     # Continuously checks for operator overrride to return to manual control while allowing time to fly to next point
        if vehicle.channels['5'] >=  1200:
            break
        time.sleep(0.5)

    if vehicle.channels['5'] >=  1200:
        break

    degree = 120 / (points_per_path - 1)  # Angle between each point (for path 1), referenced from antenna
    p1x_1 = far_field * math.sin(60)	#l ines 228-235 are used to find the necessary distance to travel to next point on the first arc
    p1y_1 = far_field * math.cos(60)
    p2x_1 = far_field * math.sin(60 - degree)
    p2y_1 = far_field * math.cos(60 - degree)
    delta_x_1 = p2x_1 - p1x_1
    delta_y_1 = p2y_1 - p1y_1
    distance_change_1 = math.sqrt(delta_x_1 ** 2 + delta_y_1 ** 2)
    time_wait_2 = (distance_change_1 / velocity) + 0.5    # Calculates time before next command is issued so drone can get to next location
    print("Time_wait_2:", time_wait_2)
    print("Time_wait_1:", time_wait_1)



    for i in range(0,total_points,1):	# Iterates through and travels to specified number of points
        if vehicle.channels['5'] >=  1200:
            break
	current_point = GPS_Coord_List[i]         # Extracts next GPS Location to go to from GPS_Coord_List
	lat_loop = current_point[0]               # Extracts the latidude of the next coordinate
        long_loop = current_point[1]              # Extracts the latidude of the next coordinate
        alt_loop = int(math.ceil(current_point[2]))               # Extracts the altitude of the next coordinate
        

        vehicle.simple_goto(LocationGlobal(lat_loop, long_loop, alt_loop),groundspeed = 1)
        print("Traveling to point: ", i)
        print("Lat: ",lat_loop)
        print("Lon: ", long_loop)
        print("Alt: ",  alt_loop)
        print(vehicle.location.global_frame.alt)

        for t in range(1,int(math.ceil(time_wait_2)) * 2, 1):     # Continuously checks for operator overrride to return to manual control while giving time to go to next point
            if vehicle.channels['5'] >=  1200:
                break
            time.sleep(0.5)
            
        print("Starting measurements for point %d" % i)
        data.saveSignal(i, antenna_frequency, file_path)
        print("Move to next point.")



    for t in range(1,1000, 1):                      # Drone waits for operator to take control once it has completed the path
        if vehicle.channels['5'] >=  1200:
            break
        time.sleep(0.5)


############################################################################################
# Manual Control
vehicle.mode = VehicleMode("STABILIZE")
vehicle.flush		# Returns control back to user, in case of malfunction or end of flight path
