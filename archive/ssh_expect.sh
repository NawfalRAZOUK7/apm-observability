#!/usr/bin/expect -f

# SSH automation script for pgBackRest
# Automatically inputs password when prompted

set timeout 30
set host "db"
set user "postgres"
set password "apm"

# Handle pgBackRest version check
if {[lindex $argv 0] == "--version"} {
    exec ssh -V
    exit 0
}

spawn ssh -o StrictHostKeyChecking=no $user@$host {*}$argv

expect {
    "password:" {
        send "$password\r"
        exp_continue
    }
    eof
}

# Exit with the same code as the spawned command
catch wait result
exit [lindex $result 3]