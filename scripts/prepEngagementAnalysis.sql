CREATE DATABASE IF NOT EXISTS Misc;
DROP TABLE IF EXISTS Misc.Activities;
CREATE TABLE  Misc.Activities
SELECT course_display_name,anon_screen_name,event_type,time
FROM Edx.EventXtract
UNION
     SELECT course_display_name,
            anon_screen_name,
	    'forum' AS event_type,
	    created_at AS time
      FROM EdxPrivate.ForumRaw
GROUP BY course_display_name
ORDER BY anon_screen_name;

use Misc;
ALTER TABLE Activities
ADD COLUMN isVideo TINYINT NOT NULL DEFAULT 0;

UPDATE Activities
SET isVideo = 1
WHERE event_type = "load_video"
   OR event_type = "play_video"
   OR event_type = "pause_video"
   OR event_type = "seek_video"
   OR event_type = "speed_change_video";

# Find course begin and end times:
DROP TABLE IF EXISTS CourseRuntimes;
CREATE TABLE CourseRuntimes
       (course_display_name varchar(255),
        course_start_date DATETIME,
	course_end_date DATETIME
	)
  SELECT course_display_name, 
  	  MIN(time) AS course_start_date,
  	  DATE_ADD(MAX(time), INTERVAL 1 WEEK) AS course_end_date
     FROM Edx.EventXtract 
     WHERE event_type = "load_video"
     GROUP BY course_display_name
     ORDER BY video_code;


# Just testing:
SELECT course_display_name, 
          video_code, 
	  MIN(time) AS course_start_date,
	  DATE_ADD(MAX(time), INTERVAL 1 WEEK) AS course_end_date
   FROM Edx.EventXtract 
   WHERE event_type = "load_video"
     AND course_display_name = "Engineering/Solar/Fall2013"
   ORDER BY video_code;
