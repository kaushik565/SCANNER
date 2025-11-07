#!/bin/bash

if [ -e /tmp/onbrdkill ]
then
	nohup pkill onboard &
else
	touch /tmp/onbrdkill
fi
