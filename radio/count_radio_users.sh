#!/bin/bash
cat /var/log/nginx/access.log | grep "/radio/" | awk '{print $1}' | sort -u 
