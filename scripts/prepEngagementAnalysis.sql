# Copyright (c) 2014, Stanford University
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

-- Create database Misc, and populate it with
-- table Activities that is needed for computing
-- student time engagement (engagement.py)

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
      FROM EdxForum.contents
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

-- The following is obsolete, but I couldn't
-- get myself to delete:

-- Find course begin and end times:
-- DROP TABLE IF EXISTS CourseRuntimes;
-- CREATE TABLE CourseRuntimes
--        (course_display_name varchar(255),
--         course_start_date DATETIME,
-- 	course_end_date DATETIME
-- 	)
--   SELECT course_display_name, 
--   	  MIN(time) AS course_start_date,
--   	  DATE_ADD(MAX(time), INTERVAL 1 WEEK) AS course_end_date
--      FROM Edx.EventXtract 
--      WHERE event_type = "load_video"
--      GROUP BY course_display_name
--      ORDER BY video_code;


-- # Just testing:
-- SELECT course_display_name, 
--           video_code, 
-- 	  MIN(time) AS course_start_date,
-- 	  DATE_ADD(MAX(time), INTERVAL 1 WEEK) AS course_end_date
--    FROM Edx.EventXtract 
--    WHERE event_type = "load_video"
--      AND course_display_name = "Engineering/Solar/Fall2013"
--    ORDER BY video_code;
