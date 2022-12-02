odoo.define('gg_account_budget.account_budget_reporting', function (require) {
    'use strict';
    var AbstractAction = require('web.AbstractAction');
    var ajax = require('web.ajax');
    var core = require('web.core');
    var rpc = require('web.rpc');
    var web_client = require('web.web_client');
    var _t = core._t;
    var QWeb = core.qweb;
    var self = this;
    var labels = ['planned_year', 'planned_month', 'practical_year', 'practical_month', 'committed_year', 'committed_month']
    var currency = rpc.query({
        model: "gg.crossovered.budget", method: "get_currency"
    })
        .then(function (result) {

            currency = result;
        });
    var ActionMenu = AbstractAction.extend({
        contentTemplate: 'Budgetdashboard',
        events: {
            'change #filter_date': 'onclick_filter_date',
        }, onclick_filter_date: function (arg) {
            var self = this;
            var filter_date = self.getDate();
            self.get_budget_reporting_this_year(filter_date);
            self.get_budget_post_reporting_table(filter_date);
            self.get_budget_by_last_five_year(filter_date);
        }, get_budget_reporting_this_year: function (arg) {
            var self = this;
            rpc.query({
                model: "gg.crossovered.budget", method: "get_budget_reporting_this_year", args: [arg]
            })
                .then(function (result) {
                    labels.forEach(function (label) {
                        var amount_item = self.format_currency(currency, result['total_' + label]);
                        let item = '';
                        if (label.includes('year')) {
                            item = 'Montant annuel';
                        } else if (label.includes('month')) {
                            item = 'Montant mensuel';
                        }
                        $('#total_' + label).empty();
                        $('#total_' + label).append('<span>' + amount_item + '</span><div class="title">' + item + '</div>')

                    });
                })
        }, get_budget_post_reporting_table: function (arg) {
            var self = this;
            rpc.query({
                model: "gg.crossovered.budget", method: "get_budget_post_reporting_table", args: [arg]
            }).then(function (result) {
                $('#budget_post_reporting').empty();

                _.forEach(result, function (x) {
                    $('#budget_post_reporting').show();
                    $('#budget_post_reporting').append('<tr>' + '<th scope="row" id="line_' + x.name + '" data-user-id="' + x.name + '" class="text-left">' + x.name + '</th>' + '<td id="line_' + x.name + '" data-user-id="' + x.name + '" class="text-right">' + self.format_currency(currency, x.total_planned_year) + '</td>' + '<td id="line_' + x.name + '" data-user-id="' + x.name + '" class="text-right">' + self.format_currency(currency, x.total_practical_year) + '</td>' + '<td id="line_' + x.name + '" data-user-id="' + x.name + '" class="text-right">' + self.format_currency(currency, x.total_committed_year) + '</td>' + '<td id="line_' + x.name + '" data-user-id="' + x.name + '" class="text-right">' + self.format_currency(currency, x.total_available_year) + '</td>' + '</tr>');
                });
            })
        }, get_budget_by_last_five_year: function (param) {
            var self = this;
            rpc.query({
                model: "gg.crossovered.budget", method: "get_budget_by_last_five_year", args: [param],
            })
                .then(function (result) {
                    var ctx = document.getElementById("canvas").getContext('2d');

                    // Define the data
                    var labels = result.labels; // Add labels to array
                    // End Defining data

                    // End Defining data
                    if (window.myCharts != undefined) window.myCharts.destroy();
                    window.myCharts = new Chart(ctx, {
                        //var myChart = new Chart(ctx, {
                        type: 'bar', data: {
                            labels: labels, datasets: [{
                                label: 'Montant Planifié',
                                data: result.datasets.total_planned_year,
                                backgroundColor: 'rgb(103, 183, 220)',
                            }, {
                                label: 'Montant Engagé',
                                data: result.datasets.total_practical_year,
                                backgroundColor: 'rgb(103, 148, 220)',
                            }, {
                                label: 'Montant Realisé',
                                data: result.datasets.total_committed_year,
                                backgroundColor: 'rgb(128, 103, 220)',
                            },]
                        }, options: {
                            responsive: true, // Instruct chart js to respond nicely.
                            maintainAspectRatio: false, // Add to prevent default behaviour of full-width/height
                            y: {
                                beginAtZero: true
                            }
                        }
                    });

                })
        },
        getDate: function () {
            var filter_date = $("#filter_date").val();
            if (filter_date === undefined) {
                var today = new Date();
                $("#filter_date").value = today.getDate() + "/" + (today.getMonth() + 1) + "/" + today.getFullYear()
            }
            return filter_date
        },
        renderElement: function () {
            var self = this;
            $.when(this._super())
                .then(function (ev) {
                    var filter_date = self.getDate();
                    self.get_budget_reporting_this_year(filter_date);
                    self.get_budget_post_reporting_table(filter_date);
                    self.get_budget_by_last_five_year(filter_date);
                });
        }, format_currency: function (currency, amount) {
            if (typeof (amount) != 'number') {
                amount = parseFloat(amount);
            }
            var formatted_value = (parseInt(amount)).toLocaleString(currency.language, {
                minimumFractionDigits: 0
            })
            if (currency.position === "after") {
                return formatted_value += ' ' + currency.symbol;
            } else {
                return currency.symbol + ' ' + formatted_value;
            }
        },
        willStart: function () {
            var self = this;
            self.drpdn_show = false;
            return Promise.all([ajax.loadLibs(this), this._super()]);
        },
    });
    core.action_registry.add('account_budget_report', ActionMenu);

});