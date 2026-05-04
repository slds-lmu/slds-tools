#
# .zshrc is sourced in interactive shells.
# It should contain commands to set up aliases,
# functions, options, key bindings, etc.
#

autoload -U compinit
compinit


# disable ctrl-d to logout
setopt IGNORE_EOF

#allow tab completion in the middle of a word
setopt COMPLETE_IN_WORD

## keep background processes at full speed
#setopt NOBGNICE
## restart running processes on exit
#setopt HUP

## history
#setopt APPEND_HISTORY
## for sharing history between zsh processes
setopt INC_APPEND_HISTORY
setopt SHARE_HISTORY
setopt nohup
## never ever beep ever
#setopt NO_BEEP

## automatically decide when to page a list of completions
#LISTMAX=0

## disable mail checking
#MAILCHECK=0

# autoload -U colors
#colors
# Lines configured by zsh-newuser-install
HISTFILE=~/.histfile
HISTSIZE=1000000000
SAVEHIST=10000000000
setopt extendedglob nomatch
unsetopt beep autocd
bindkey -e
# End of lines configured by zsh-newuser-install
# The following lines were added by compinstall
zstyle :compinstall filename ~/.zshrc

autoload -Uz compinit
compinit
# End of lines added by compinstall


alias 'lsp'='ps ax | grep '

autoload -U colors && colors

PROMPT='%h %# '
case $TERM in
        *rxvt*)
            
            precmd () {print -rP "[%(?.%{$fg[green]%}.%{$bg[red]%}%{$fg[white]%})%?%{$reset_color%}]%(1j.|%j|.)[%n @%m %D{%F} %B%D{%T}%b] %~" ; print -Pn "\e]0;urxvt :: %n :: %d\a"}
        preexec () { T0=${~1} ; T=${(q)T0} ; print -Pn "\e]0;urxvt :: %n :: %d :: ${T:gs/%/%%}\a" ;
             print -rP '>> %D{%F} %B%D{%T}%b <<'}
         ;;
    *xterm*)
            precmd () {print -rP "[%(?.%{$fg[green]%}.%{$bg[red]%}%{$fg[white]%})%?%{$reset_color%}]%(1j.|%j|.)[%n @%m %D{%F} %B%D{%T}%b] %~" ; print -Pn "\e]0;xterm :: %n :: %d\a"}
            preexec () { T0=${~1} ; T=${(q)T0} ; print -Pn "\e]0;xterm :: %n :: %d :: ${T:gs/%/%%}\a" ;
                         print -rP '>> %D{%F} %B%D{%T}%b <<'}
     ;;
    *screen*)
            precmd () {print -rP "[%(?.%{$fg[green]%}.%{$bg[red]%}%{$fg[white]%})%?%{$reset_color%}]%(1j.|%j|.)[%n @%m %D{%F} %B%D{%T}%b] %~" ; print -Pn "\033]2;zsh :: %n :: %d\033\\"}
            preexec () { T0=${~1} ; T=${(q)T0} ; print -Pn "\033]2;zsh :: %n :: %d :: ${T:gs/%/%%}\033\\" ;
                         print -rP '>> %D{%F} %B%D{%T}%b <<'}
     ;;
    *linux*)
            precmd () {print -rP "[%(?.%{$fg[green]%}.%{$bg[red]%}%{$fg[white]%})%?%{$reset_color%}]%(1j.|%j|.)[%n @%m %D{%F} %B%D{%T}%b] %~" }
            preexec () { T0=${~1} ; T=${(q)T0} ;
                         print -rP '>> %D{%F} %B%D{%T}%b <<'}
         ;;

    esac

export LESS=' -R '
