/*jslint */
/*global require: false, window: false */
'use strict';

require.def('cards', ['jquery', 'text!templates/cardsHeader.html'], function ($, headerTemplate) {
    var header, display, back, nlCards,
        cardPosition = 0,
        headerText = '',
        cardTitles = [];

    function adjustCardSizes() {
        var cardWidth = display.outerWidth(),
            cardList = $('.card'),
            totalWidth = cardWidth * cardList.length,
            height = window.innerHeight - header.outerHeight();

        //Set height
        display.css('height', height + 'px');

        //Set widths and heights of cards. Need to set the heights
        //explicitly so any card using iscroll will get updated correctly.
        nlCards.css({
            width: totalWidth + 'px',
            height: height + 'px'
        });

        cardList.css({
            width: cardWidth + 'px',
            height: height + 'px'
        });

        //Reset the scroll correctly.
        cards.scroll();
    }

    function cards(nl, title) {
        nl = nl.jquery ? nl : $(nl);

        $(function () {
            //Insert the header before the cards
            header = $(headerTemplate).insertBefore(nl);
            headerText = $('#headerText');

            back = $('#back');
            back.css('display', 'none');
            back.click(cards.back);

            display = nl;
            nlCards = display.find('#cards');

            adjustCardSizes();
            cards.setTitle(title);

            //Detect orientation changes and size the card container size accordingly.
            if ('onorientationchange' in window) {
                window.addEventListener('orientationchange', adjustCardSizes, false);
            }
            window.addEventListener('resize', adjustCardSizes, false);

        });
    }

    cards.back = function () {
        cardPosition -= 1;
        if (cardPosition < 0) {
            cardPosition = 0;
        }
        cards.scroll();
    };

    cards.forward = function (title) {
        cardPosition += 1;
        cards.scroll(title);
    };

    cards.scroll = function (title) {
        if (title) {
            cardTitles[cardPosition] = title;
        }

        cards.setTitle(title);

        var left = display.outerWidth() * cardPosition;

        nlCards.css({
            left: '-' + left + 'px'
        });

        //Hide/Show back button as appropriate
        back.css('display', !cardPosition ? 'none' : '');
    };

    cards.setTitle = function (title) {
        title = title || cardTitles[cardPosition] || nlCards.find('.card').eq(cardPosition).attr('title') || '';
        headerText.html(title);
    };

    return cards;
});
