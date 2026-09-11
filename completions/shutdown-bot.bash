_shutdown_bot_completions() {
    local cur prev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    if [[ "${COMP_WORDS[1]}" == "service" && COMP_CWORD -ge 3 ]]; then
        COMPREPLY=( $(compgen -W "status start stop restart" -- "$cur") )
    elif [[ "$prev" == "poweroff" || "$prev" == "reboot" || "$prev" == "suspend" || "$prev" == "lock" ]]; then
        COMPREPLY=( $(compgen -W "--yes" -- "$cur") )
    elif [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "status service logs config poweroff reboot suspend lock" -- "$cur") )
    fi
}
complete -F _shutdown_bot_completions shutdown-bot
